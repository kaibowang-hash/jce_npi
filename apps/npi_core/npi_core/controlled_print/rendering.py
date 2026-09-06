from __future__ import annotations

import hashlib
import html
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from npi_core.controlled_print.domain import (
    ControlledPrintAuthorityUnavailable,
    ControlledPrintContext,
    ControlledPrintMappingUnavailable,
    ControlledPrintRegistryReference,
    ControlledPrintRegistryVersion,
    ControlledPrintSnapshot,
)
from npi_core.controlled_print.qr import (
    verification_qr_data_uri,
    verification_qr_digest,
)


_REMOTE_OR_ACTIVE_CONTENT = re.compile(
    r"(?:https?\s*:|ftp\s*:|file\s*:|(?<!:)//|<\s*(?:script|iframe|object|embed)\b)",
    re.IGNORECASE,
)
_MAX_RENDERED_HTML_BYTES = 2_097_152
_MAX_CONTROLLED_PDF_BYTES = 104_857_600


@dataclass(frozen=True, slots=True)
class RenderedControlledPrintPdf:
    content: bytes
    file_name: str
    mime_type: str
    size_bytes: int
    sha256: str
    verification_qr_sha256: str


def render_controlled_print_pdf(
    *,
    snapshot: ControlledPrintSnapshot,
    mapping: ControlledPrintRegistryVersion,
    render_template: Callable[[str, Mapping[str, object]], str],
    convert_pdf: Callable[[str], bytes],
    translate: Callable[[str, str], str],
) -> RenderedControlledPrintPdf:
    """Render once from only the captured template and frozen source snapshot."""

    _require_exact_mapping(snapshot, mapping)
    _deny_remote_or_active_content(mapping.template_content)
    snapshot_payload = snapshot.snapshot_payload()
    source = snapshot_payload["sourceSnapshot"]
    if not isinstance(source, Mapping):
        raise RuntimeError("Controlled print source snapshot is invalid.")
    context: dict[str, object] = {
        "doc": dict(source),
        "controlledPrint": {
            "snapshotId": str(snapshot.global_id),
            "snapshotHash": snapshot.snapshot_hash,
            "verificationPayload": snapshot.verification_payload,
            "verificationQrDataUri": verification_qr_data_uri(
                snapshot.verification_payload
            ),
            "watermark": snapshot.watermark_source,
            "actorUserId": snapshot.actor_user_id,
            "printedAt": snapshot_payload["printedAt"],
            "language": snapshot.language,
            "copyState": snapshot.copy_state.value,
        },
    }
    body = render_template(mapping.template_content, context)
    if not isinstance(body, str) or not body.strip():
        raise RuntimeError("Controlled Print Format rendered no content.")
    _deny_remote_or_active_content(body)
    verification_label = translate(
        "Controlled print verification code",
        snapshot.language,
    )
    if not isinstance(verification_label, str) or not verification_label.strip():
        raise RuntimeError("Controlled print translation is unavailable.")
    document = _controlled_shell(snapshot, body, verification_label)
    if len(document.encode("utf-8")) > _MAX_RENDERED_HTML_BYTES:
        raise RuntimeError("Controlled print rendered HTML exceeds its safe bound.")
    content = convert_pdf(document)
    if (
        not isinstance(content, bytes)
        or not content.startswith(b"%PDF-")
        or not 1 <= len(content) <= _MAX_CONTROLLED_PDF_BYTES
    ):
        raise RuntimeError("Controlled print renderer returned an invalid PDF.")
    return RenderedControlledPrintPdf(
        content=content,
        file_name=f"controlled-print-{snapshot.global_id}.pdf",
        mime_type="application/pdf",
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        verification_qr_sha256=verification_qr_digest(
            snapshot.verification_payload
        ),
    )


def frappe_render_template(
    template: str,
    context: Mapping[str, object],
) -> str:
    import frappe

    rendered = frappe.render_template(template, dict(context))
    if not isinstance(rendered, str):
        raise RuntimeError("Frappe Print Format returned invalid HTML.")
    return rendered


def frappe_convert_pdf(document: str) -> bytes:
    from frappe.utils.weasyprint import import_weasyprint

    HTML, _CSS = import_weasyprint()
    # The controlled shell is self-contained and rejects remote/active content.
    # Do not give the renderer a base URL that could resolve ambient Site assets.
    content = HTML(string=document).write_pdf()
    if isinstance(content, bytearray):
        return bytes(content)
    return content


def frappe_translate(source: str, language: str) -> str:
    from frappe import _

    _("Controlled print verification code")
    if language == "en":
        return source
    from frappe.translate import get_all_translations

    translated = get_all_translations(language).get(source)
    if not isinstance(translated, str) or not translated.strip():
        raise RuntimeError("Controlled print translation is unavailable.")
    return translated


def _require_exact_mapping(
    snapshot: ControlledPrintSnapshot,
    mapping: ControlledPrintRegistryVersion,
) -> None:
    context = ControlledPrintContext(
        tenant_id=snapshot.tenant_id,
        project_global_id=snapshot.project_global_id,
        source_object_type=snapshot.source.source_object_type,
        project_type_key=snapshot.project_type_key,
        gate_key=snapshot.gate_key,
        source_state=snapshot.source.source_state,
        language=snapshot.language,
        delivery_mode=snapshot.delivery_mode,
        copy_state=snapshot.copy_state,
    )
    if (
        not mapping.matches(context, snapshot.printed_at)
        or ControlledPrintRegistryReference.from_mapping(mapping) != snapshot.registry
        or mapping.watermark_source != snapshot.watermark_source
    ):
        raise ControlledPrintMappingUnavailable()
    if not mapping.authorizes(snapshot.actor_user_id):
        raise ControlledPrintAuthorityUnavailable()


def _controlled_shell(
    snapshot: ControlledPrintSnapshot,
    body: str,
    verification_label: str,
) -> str:
    qr_uri = verification_qr_data_uri(snapshot.verification_payload)
    escaped = {
        "actor": html.escape(snapshot.actor_user_id),
        "hash": html.escape(snapshot.snapshot_hash),
        "payload": html.escape(snapshot.verification_payload),
        "printed": html.escape(
            str(snapshot.snapshot_payload()["printedAt"]),
        ),
        "watermark": html.escape(snapshot.watermark_source),
        "verification_label": html.escape(verification_label),
    }
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><style>"
        "@page{size:A4;margin:18mm 14mm 22mm}"
        "body{font-family:sans-serif;color:#1f2933;font-size:10pt}"
        ".npi-controlled{position:relative;min-height:240mm}"
        ".npi-watermark{position:fixed;inset:42% 0 auto;text-align:center;"
        "font-size:34pt;color:#d5dadd;transform:rotate(-28deg);z-index:-1}"
        ".npi-verification{margin-top:8mm;padding-top:4mm;border-top:1px solid #60717c;"
        "display:grid;grid-template-columns:34mm 1fr;gap:4mm;align-items:start}"
        ".npi-verification img{width:30mm;height:30mm}"
        ".npi-meta{font-size:8pt;line-height:1.45;overflow-wrap:anywhere}"
        "</style></head><body><main class=\"npi-controlled\">"
        f"<div class=\"npi-watermark\">{escaped['watermark']}</div>"
        f"<section class=\"npi-body\">{body}</section>"
        "<footer class=\"npi-verification\">"
        f"<img src=\"{qr_uri}\" alt=\"{escaped['verification_label']}\">"
        "<div class=\"npi-meta\">"
        f"<div>{escaped['payload']}</div><div>{escaped['hash']}</div>"
        f"<div>{escaped['actor']}</div><div>{escaped['printed']}</div>"
        "</div></footer></main></body></html>"
    )


def _deny_remote_or_active_content(value: str) -> None:
    if _REMOTE_OR_ACTIVE_CONTENT.search(value):
        raise RuntimeError(
            "Controlled Print Format contains remote or active content."
        )
