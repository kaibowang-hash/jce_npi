import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type {
  CreateEngineeringBomCommand,
  EngineeringBomChangeType,
  EngineeringBomCommandViewModel,
  EngineeringBomComparisonViewModel,
  EngineeringBomDataSource,
  EngineeringBomDetailViewModel,
  EngineeringBomLifecycleState,
  EngineeringBomLineInput,
  EngineeringBomListViewModel,
  EngineeringBomPolicyOptionViewModel,
  EngineeringBomRevisionViewModel,
} from "../api/ebom-data-source";
import { EngineeringBomRequestCancelledError } from "../api/ebom-data-source";
import type { EngineeringBomPublishRequestDataSource } from "../api/publish-request-data-source";
import type { ItemPublishDataSource } from "../api/item-publish-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { ReportWorkspaceDirty } from "../app/workspace-navigation";
import { DockedInspector } from "../components/object-components";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  Panel,
  SemanticStatus,
} from "../components/primitives";
import {
  formatDate,
  formatDateTime,
  formatDecimal,
  formatNumber,
} from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";
import { EngineeringBomPublishRequestWorkspace } from "./project-ebom-publish-workspace";

type ResourceState<T> =
  | { kind: "loading" }
  | { kind: "loaded"; value: T }
  | { kind: "failed"; failure: RequestFailure };

type DetailState =
  | ResourceState<EngineeringBomDetailViewModel>
  | { kind: "idle" };
type ComparisonState =
  | ResourceState<EngineeringBomComparisonViewModel>
  | { kind: "idle" };
type EditorKind =
  | "create"
  | "revise"
  | "submit"
  | "review"
  | "release"
  | "compare"
  | null;
type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "failed"; failure: RequestFailure };

interface EngineeringBomLineDraft {
  clientKey: string;
  lineKey: string;
  parentLineKey: string;
  engineeringItemId: string;
  description: string;
  quantity: string;
  engineeringUom: string;
  alternateForLineKey: string;
  alternateGroupKey: string;
  effectivityStart: string;
  effectivityEnd: string;
  attributesText: string;
}

interface RevisionFormState {
  reason: string;
  effectivityNote: string;
  lines: readonly EngineeringBomLineDraft[];
}

const emptyLine = (): EngineeringBomLineDraft => ({
  clientKey: globalThis.crypto.randomUUID(),
  lineKey: "",
  parentLineKey: "",
  engineeringItemId: "",
  description: "",
  quantity: "1",
  engineeringUom: "",
  alternateForLineKey: "",
  alternateGroupKey: "",
  effectivityStart: "",
  effectivityEnd: "",
  attributesText: "",
});

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    Boolean(failure.problem?.retryable) ||
    failure.problem?.status === 409
  );
}

function lifecycleLabel(
  t: ReturnType<typeof useI18n>["t"],
  state: EngineeringBomLifecycleState,
): string {
  switch (state) {
    case "draft":
      return t("Draft");
    case "in_review":
      return t("In review");
    case "approved":
      return t("Approved");
    case "released":
      return t("Released");
  }
}

function changeTypeLabel(
  t: ReturnType<typeof useI18n>["t"],
  changeType: EngineeringBomChangeType,
): string {
  switch (changeType) {
    case "added":
      return t("Added");
    case "removed":
      return t("Removed");
    case "quantity":
      return t("Quantity changed");
    case "substitution":
      return t("Substitution changed");
    case "attribute":
      return t("Attributes changed");
  }
}

function draftFromRevision(
  revision: EngineeringBomRevisionViewModel,
): RevisionFormState {
  return {
    reason: "",
    effectivityNote: revision.effectivityNote ?? "",
    lines: revision.lines.map((line) => ({
      clientKey: line.globalId,
      lineKey: line.lineKey,
      parentLineKey: line.parentLineKey ?? "",
      engineeringItemId: line.engineeringItemId,
      description: line.description,
      quantity: line.quantity,
      engineeringUom: line.engineeringUom,
      alternateForLineKey: line.alternateForLineKey ?? "",
      alternateGroupKey: line.alternateGroupKey ?? "",
      effectivityStart: line.effectivityStart ?? "",
      effectivityEnd: line.effectivityEnd ?? "",
      attributesText: Object.entries(line.attributes)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, value]) => `${key}=${value}`)
        .join("; "),
    })),
  };
}

function parseAttributes(
  value: string,
): Readonly<Record<string, string>> | null {
  const result: Record<string, string> = {};
  const entries = value
    .split(";")
    .map((entry) => entry.trim())
    .filter(Boolean);
  for (const entry of entries) {
    const separator = entry.indexOf("=");
    if (separator <= 0) return null;
    const key = entry.slice(0, separator).trim();
    const attributeValue = entry.slice(separator + 1).trim();
    if (!/^[a-z][a-z0-9_.-]{0,63}$/u.test(key) || key in result) return null;
    result[key] = attributeValue;
  }
  return result;
}

function linesFromDrafts(
  drafts: readonly EngineeringBomLineDraft[],
): readonly EngineeringBomLineInput[] | null {
  const lines: EngineeringBomLineInput[] = [];
  for (const draft of drafts) {
    const attributes = parseAttributes(draft.attributesText);
    if (!attributes) return null;
    lines.push({
      lineKey: draft.lineKey.trim(),
      parentLineKey: draft.parentLineKey.trim() || null,
      engineeringItemId: draft.engineeringItemId.trim(),
      description: draft.description.trim(),
      quantity: draft.quantity.trim(),
      engineeringUom: draft.engineeringUom.trim(),
      alternateForLineKey: draft.alternateForLineKey.trim() || null,
      alternateGroupKey: draft.alternateGroupKey.trim() || null,
      effectivityStart: draft.effectivityStart || null,
      effectivityEnd: draft.effectivityEnd || null,
      attributes,
    });
  }
  return lines;
}

function policyValue(policy: EngineeringBomPolicyOptionViewModel): string {
  return `${policy.globalId}:${String(policy.version)}:${policy.snapshotHash}`;
}

function selectedPolicy(
  policies: readonly EngineeringBomPolicyOptionViewModel[],
  value: string,
): EngineeringBomPolicyOptionViewModel | null {
  return policies.find((policy) => policyValue(policy) === value) ?? null;
}

function editorFocusTarget(element: HTMLElement | null): HTMLElement | null {
  if (!element) return null;
  if (element.matches("button, input, select, textarea, [tabindex]")) {
    return element;
  }
  return element.querySelector<HTMLElement>(
    "button, input, select, textarea, [tabindex]",
  );
}

function LoadingSurface({ label }: { label: string }): React.JSX.Element {
  return (
    <section
      aria-busy="true"
      aria-label={label}
      className="workspace-resource-state workspace-resource-state--loading"
      role="status"
    >
      <div className="skeleton skeleton--title" />
      <div className="skeleton" />
      <div className="skeleton" />
      <span className="visually-hidden">{label}</span>
    </section>
  );
}

function FailureSurface({
  failure,
  retry,
}: {
  failure: RequestFailure;
  retry: () => void;
}): React.JSX.Element {
  const { t } = useI18n();
  return (
    <section className="workspace-resource-state" role="alert">
      <SemanticStatus label={t("Error")} tone="danger" />
      <RequestFailurePanel failure={failure} />
      {canRetry(failure) ? (
        <Button icon="refresh" onClick={retry} visual="primary">
          {failure.problem?.status === 409 ? t("Reload") : t("Retry")}
        </Button>
      ) : null}
    </section>
  );
}

function CommandStatus({
  retry,
  state,
}: {
  retry: () => void;
  state: CommandState;
}): React.JSX.Element | null {
  const { t } = useI18n();
  if (state.kind === "idle") return null;
  if (state.kind === "processing") {
    return (
      <div aria-live="polite" className="ebom-workspace__command" role="status">
        <SemanticStatus label={t("Processing")} tone="info" />
        <span>{state.label}</span>
      </div>
    );
  }
  return (
    <div className="ebom-workspace__command" role="alert">
      <SemanticStatus label={t("Command failed")} tone="danger" />
      <RequestFailurePanel failure={state.failure} />
      {canRetry(state.failure) ? (
        <Button icon="refresh" onClick={retry}>
          {state.failure.problem?.status === 409 ? t("Reload") : t("Retry")}
        </Button>
      ) : null}
    </div>
  );
}

function LineEditor({
  lines,
  maximumNodes,
  onChange,
  policy,
}: {
  lines: readonly EngineeringBomLineDraft[];
  maximumNodes: number;
  onChange: (lines: readonly EngineeringBomLineDraft[]) => void;
  policy: EngineeringBomPolicyOptionViewModel;
}): React.JSX.Element {
  const { t } = useI18n();
  const changeLine = (
    index: number,
    field: keyof EngineeringBomLineDraft,
    value: string,
  ): void => {
    onChange(
      lines.map((line, lineIndex) =>
        lineIndex === index ? { ...line, [field]: value } : line,
      ),
    );
  };
  return (
    <div className="ebom-line-editor">
      <div className="ebom-line-editor__toolbar">
        <span>
          {t("Lines")}: {String(lines.length)} / {String(maximumNodes)}
        </span>
        <Button
          disabled={lines.length >= maximumNodes}
          icon="add"
          onClick={() => {
            onChange([...lines, emptyLine()]);
          }}
          type="button"
        >
          {t("Add line")}
        </Button>
      </div>
      <div className="ebom-line-editor__scroll">
        <table className="data-table data-table--compact">
          <thead>
            <tr>
              <th>{t("Line key")}</th>
              <th>{t("Parent line")}</th>
              <th>{t("Engineering item")}</th>
              <th>{t("Description")}</th>
              <th>{t("Quantity")}</th>
              <th>{t("Engineering UOM")}</th>
              <th>{t("Alternate for")}</th>
              <th>{t("Alternate group")}</th>
              <th>{t("Effective from")}</th>
              <th>{t("Effective to")}</th>
              <th>{t("Attributes")}</th>
              <th>{t("Actions")}</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => (
              <tr key={line.clientKey}>
                <td>
                  <TextInput
                    aria-label={t("Line {{number}} key", {
                      number: String(index + 1),
                    })}
                    maxLength={64}
                    onChange={(event) => {
                      changeLine(index, "lineKey", event.currentTarget.value);
                    }}
                    required
                    value={line.lineKey}
                  />
                </td>
                <td>
                  <TextInput
                    aria-label={t("Line {{number}} parent", {
                      number: String(index + 1),
                    })}
                    maxLength={64}
                    onChange={(event) => {
                      changeLine(
                        index,
                        "parentLineKey",
                        event.currentTarget.value,
                      );
                    }}
                    value={line.parentLineKey}
                  />
                </td>
                <td>
                  <TextInput
                    aria-label={t("Line {{number}} engineering item", {
                      number: String(index + 1),
                    })}
                    maxLength={128}
                    onChange={(event) => {
                      changeLine(
                        index,
                        "engineeringItemId",
                        event.currentTarget.value,
                      );
                    }}
                    required
                    value={line.engineeringItemId}
                  />
                </td>
                <td>
                  <TextInput
                    aria-label={t("Line {{number}} description", {
                      number: String(index + 1),
                    })}
                    maxLength={280}
                    onChange={(event) => {
                      changeLine(
                        index,
                        "description",
                        event.currentTarget.value,
                      );
                    }}
                    required
                    value={line.description}
                  />
                </td>
                <td>
                  <TextInput
                    aria-label={t("Line {{number}} quantity", {
                      number: String(index + 1),
                    })}
                    inputMode="decimal"
                    maxLength={64}
                    onChange={(event) => {
                      changeLine(index, "quantity", event.currentTarget.value);
                    }}
                    required
                    value={line.quantity}
                  />
                </td>
                <td>
                  <Select
                    aria-label={t("Line {{number}} engineering UOM", {
                      number: String(index + 1),
                    })}
                    onChange={(event) => {
                      changeLine(
                        index,
                        "engineeringUom",
                        event.currentTarget.value,
                      );
                    }}
                    required
                    value={line.engineeringUom}
                  >
                    <option value="">{t("Select UOM")}</option>
                    {policy.engineeringUoms.map((uom) => (
                      <option data-language-exempt="unit" key={uom} value={uom}>
                        {uom}
                      </option>
                    ))}
                  </Select>
                </td>
                <td>
                  <TextInput
                    aria-label={t("Line {{number}} alternate target", {
                      number: String(index + 1),
                    })}
                    maxLength={64}
                    onChange={(event) => {
                      changeLine(
                        index,
                        "alternateForLineKey",
                        event.currentTarget.value,
                      );
                    }}
                    value={line.alternateForLineKey}
                  />
                </td>
                <td>
                  <TextInput
                    aria-label={t("Line {{number}} alternate group", {
                      number: String(index + 1),
                    })}
                    maxLength={64}
                    onChange={(event) => {
                      changeLine(
                        index,
                        "alternateGroupKey",
                        event.currentTarget.value,
                      );
                    }}
                    value={line.alternateGroupKey}
                  />
                </td>
                <td>
                  <TextInput
                    aria-label={t("Line {{number}} effective from", {
                      number: String(index + 1),
                    })}
                    onChange={(event) => {
                      changeLine(
                        index,
                        "effectivityStart",
                        event.currentTarget.value,
                      );
                    }}
                    type="date"
                    value={line.effectivityStart}
                  />
                </td>
                <td>
                  <TextInput
                    aria-label={t("Line {{number}} effective to", {
                      number: String(index + 1),
                    })}
                    onChange={(event) => {
                      changeLine(
                        index,
                        "effectivityEnd",
                        event.currentTarget.value,
                      );
                    }}
                    type="date"
                    value={line.effectivityEnd}
                  />
                </td>
                <td>
                  <TextInput
                    aria-label={t("Line {{number}} attributes", {
                      number: String(index + 1),
                    })}
                    maxLength={2000}
                    onChange={(event) => {
                      changeLine(
                        index,
                        "attributesText",
                        event.currentTarget.value,
                      );
                    }}
                    placeholder={t("key=value; key=value")}
                    value={line.attributesText}
                  />
                </td>
                <td>
                  <Button
                    aria-label={t("Remove line {{number}}", {
                      number: String(index + 1),
                    })}
                    disabled={lines.length === 1}
                    icon="clear"
                    onClick={() => {
                      onChange(
                        lines.filter(
                          (_value, lineIndex) => lineIndex !== index,
                        ),
                      );
                    }}
                    type="button"
                  >
                    {t("Remove")}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <small>
        {t(
          "Line identity, hierarchy, alternates, effectivity, quantities and attributes are validated by the exact EBOM policy.",
        )}
      </small>
    </div>
  );
}

export function ProjectEngineeringBomWorkspace({
  dataSource,
  itemPublishDataSource,
  publishRequestDataSource,
  projectId,
  reportWorkspaceDirty,
}: {
  dataSource?: EngineeringBomDataSource | undefined;
  itemPublishDataSource?: ItemPublishDataSource | undefined;
  publishRequestDataSource?: EngineeringBomPublishRequestDataSource | undefined;
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [listAttempt, setListAttempt] = useState(0);
  const [detailAttempt, setDetailAttempt] = useState(0);
  const [listState, setListState] = useState<
    ResourceState<EngineeringBomListViewModel>
  >({
    kind: "loading",
  });
  const [detailState, setDetailState] = useState<DetailState>({ kind: "idle" });
  const [comparisonState, setComparisonState] = useState<ComparisonState>({
    kind: "idle",
  });
  const [selectedEbomId, setSelectedEbomId] = useState<string | null>(null);
  const [selectedRevisionId, setSelectedRevisionId] = useState<string | null>(
    null,
  );
  const [editor, setEditor] = useState<EditorKind>(null);
  const [editorTouched, setEditorTouched] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [commandState, setCommandState] = useState<CommandState>({
    kind: "idle",
  });
  const [publishDirty, setPublishDirty] = useState(false);
  const [policyRef, setPolicyRef] = useState("");
  const [engineeringBomKey, setEngineeringBomKey] = useState("");
  const [title, setTitle] = useState("");
  const [revisionForm, setRevisionForm] = useState<RevisionFormState>({
    reason: "",
    effectivityNote: "",
    lines: [emptyLine()],
  });
  const [transitionReason, setTransitionReason] = useState("");
  const [reviewDecision, setReviewDecision] = useState<"approve" | "reject">(
    "approve",
  );
  const [releaseConfirmed, setReleaseConfirmed] = useState(false);
  const [comparisonSelection, setComparisonSelection] = useState({
    fromRevisionId: "",
    toRevisionId: "",
  });
  const firstEditorControl = useRef<HTMLElement | null>(null);
  const returnFocus = useRef<HTMLElement | null>(null);
  const latestCommand = useRef<(() => void) | null>(null);
  const list = listState.kind === "loaded" ? listState.value : null;
  const detail = detailState.kind === "loaded" ? detailState.value : null;
  const selectedRevision = useMemo(
    () =>
      detail?.revisions.find(
        (revision) => revision.globalId === selectedRevisionId,
      ) ??
      detail?.revisions[0] ??
      null,
    [detail?.revisions, selectedRevisionId],
  );
  const dirty =
    (editor !== null && editor !== "compare" && editorTouched) || publishDirty;
  const commandProcessing = commandState.kind === "processing";

  const closeEditor = useCallback((): void => {
    setEditor(null);
    setEditorTouched(false);
    setFormError(null);
    setTransitionReason("");
    setReleaseConfirmed(false);
    const target = returnFocus.current;
    globalThis.queueMicrotask(() => target?.focus());
  }, []);

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!dirty) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity: selectedEbomId ?? `${projectId}:new-ebom`,
      version: selectedRevision
        ? `ebom-revision-${String(selectedRevision.revisionNumber)}`
        : "unsaved-ebom",
      returnFocusTarget: () =>
        (publishDirty
          ? document.querySelector<HTMLElement>(
              ".publish-request__form select, .publish-request__form input",
            )
          : editorFocusTarget(firstEditorControl.current)) ??
        document.getElementById("project-workspace-tab-ebom"),
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [
    dirty,
    projectId,
    publishDirty,
    reportWorkspaceDirty,
    selectedEbomId,
    selectedRevision,
  ]);

  useEffect(() => {
    if (!dataSource) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadEboms(projectId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setListState({ kind: "loaded", value });
        setSelectedEbomId(
          (current) => current ?? value.items[0]?.globalId ?? null,
        );
        setPolicyRef(
          (current) =>
            current ||
            (value.policies[0] ? policyValue(value.policies[0]) : ""),
        );
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof EngineeringBomRequestCancelledError
        )
          return;
        setListState({ failure: toRequestFailure(error), kind: "failed" });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, listAttempt, projectId]);

  useEffect(() => {
    if (!dataSource || !selectedEbomId) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadEbom(projectId, selectedEbomId, controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return;
        setDetailState({ kind: "loaded", value });
        const initialRevision = value.revisions[0] ?? null;
        setSelectedRevisionId(initialRevision?.globalId ?? null);
        setComparisonSelection({
          fromRevisionId: value.revisions[1]?.globalId ?? "",
          toRevisionId: initialRevision?.globalId ?? "",
        });
        setComparisonState({ kind: "idle" });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof EngineeringBomRequestCancelledError
        )
          return;
        setDetailState({ failure: toRequestFailure(error), kind: "failed" });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, detailAttempt, projectId, selectedEbomId]);

  const reload = useCallback((): void => {
    closeEditor();
    setCommandState({ kind: "idle" });
    setComparisonState({ kind: "idle" });
    setListState({ kind: "loading" });
    setListAttempt((current) => current + 1);
    if (selectedEbomId) {
      setDetailState({ kind: "loading" });
      setDetailAttempt((current) => current + 1);
    }
  }, [closeEditor, selectedEbomId]);

  const acceptCommand = useCallback(
    (value: EngineeringBomCommandViewModel): void => {
      setSelectedEbomId(value.ebom.globalId);
      setSelectedRevisionId(value.revision.globalId);
      setListState((current) => {
        if (current.kind !== "loaded") return current;
        const items = current.value.items.some(
          (item) => item.globalId === value.ebom.globalId,
        )
          ? current.value.items.map((item) =>
              item.globalId === value.ebom.globalId ? value.ebom : item,
            )
          : [value.ebom, ...current.value.items];
        return { kind: "loaded", value: { ...current.value, items } };
      });
      closeEditor();
      setCommandState({ kind: "idle" });
      setDetailState({ kind: "loading" });
      setDetailAttempt((current) => current + 1);
    },
    [closeEditor],
  );

  const runCommand = useCallback(
    (
      label: string,
      command: (signal: AbortSignal) => Promise<EngineeringBomCommandViewModel>,
    ): void => {
      const run = (): void => {
        const controller = new AbortController();
        setCommandState({ kind: "processing", label });
        void command(controller.signal)
          .then(acceptCommand)
          .catch((error: unknown) => {
            if (
              controller.signal.aborted ||
              error instanceof EngineeringBomRequestCancelledError
            )
              return;
            setCommandState({
              failure: toRequestFailure(error),
              kind: "failed",
            });
          });
      };
      latestCommand.current = run;
      run();
    },
    [acceptCommand],
  );

  const startEditor = (
    kind: Exclude<EditorKind, null>,
    trigger: HTMLElement,
  ): void => {
    returnFocus.current = trigger;
    setFormError(null);
    setEditorTouched(false);
    if (kind === "create") {
      const policy = list?.policies[0];
      setPolicyRef(policy ? policyValue(policy) : "");
      setEngineeringBomKey("");
      setTitle("");
      setRevisionForm({
        reason: "",
        effectivityNote: "",
        lines: [emptyLine()],
      });
    } else if (kind === "revise" && selectedRevision) {
      setRevisionForm(draftFromRevision(selectedRevision));
    }
    setTransitionReason("");
    setReviewDecision("approve");
    setReleaseConfirmed(false);
    setEditor(kind);
    globalThis.queueMicrotask(() =>
      editorFocusTarget(firstEditorControl.current)?.focus(),
    );
  };

  const submitContent = (): void => {
    if (!dataSource || !list || !sessionCommandContext) return;
    const policy = selectedPolicy(list.policies, policyRef);
    const lines = linesFromDrafts(revisionForm.lines);
    if (!policy || !lines || lines.length < 1 || !revisionForm.reason.trim()) {
      setFormError(
        t(
          "Complete the exact policy, reason and every required EBOM line field before continuing.",
        ),
      );
      return;
    }
    if (editor === "create") {
      const idempotencyKey = `ebom-create-${globalThis.crypto.randomUUID()}`;
      const command: CreateEngineeringBomCommand = {
        policyGlobalId: policy.globalId,
        policyVersion: policy.version,
        policySnapshotHash: policy.snapshotHash,
        engineeringBomKey,
        title,
        reason: revisionForm.reason,
        effectivityNote: revisionForm.effectivityNote || null,
        lines,
      };
      runCommand(t("Creating EBOM"), (signal) =>
        dataSource.createEbom(projectId, command, {
          ...sessionCommandContext,
          idempotencyKey,
          signal,
        }),
      );
      return;
    }
    if (editor === "revise" && detail && selectedRevision) {
      const idempotencyKey = `ebom-revise-${globalThis.crypto.randomUUID()}`;
      runCommand(t("Creating immutable EBOM revision"), (signal) =>
        dataSource.createRevision(
          projectId,
          detail.ebom.globalId,
          {
            expectedEbomVersion: detail.ebom.optimisticVersion,
            predecessorRevisionId: selectedRevision.globalId,
            expectedPredecessorSnapshotHash: selectedRevision.snapshotHash,
            policyGlobalId: policy.globalId,
            policyVersion: policy.version,
            policySnapshotHash: policy.snapshotHash,
            reason: revisionForm.reason,
            effectivityNote: revisionForm.effectivityNote || null,
            lines,
          },
          {
            ...sessionCommandContext,
            idempotencyKey,
            signal,
          },
        ),
      );
    }
  };

  const submitTransition = (): void => {
    if (!dataSource || !detail || !selectedRevision || !sessionCommandContext)
      return;
    const common = {
      expectedEbomVersion: detail.ebom.optimisticVersion,
      expectedRevisionSnapshotHash: selectedRevision.snapshotHash,
      expectedLifecycleVersion: selectedRevision.lifecycle.version,
      policyGlobalId: selectedRevision.policy.globalId,
      policyVersion: selectedRevision.policy.version,
      policySnapshotHash: selectedRevision.policy.snapshotHash,
    };
    if (editor === "submit") {
      const idempotencyKey = `ebom-submit-${globalThis.crypto.randomUUID()}`;
      runCommand(t("Submitting EBOM for review"), (signal) =>
        dataSource.submitReview(
          projectId,
          detail.ebom.globalId,
          selectedRevision.globalId,
          { ...common, reason: transitionReason || null },
          {
            ...sessionCommandContext,
            idempotencyKey,
            signal,
          },
        ),
      );
    } else if (editor === "review") {
      if (reviewDecision === "reject" && !transitionReason.trim()) {
        setFormError(t("A rejection reason is required."));
        return;
      }
      const idempotencyKey = `ebom-review-${globalThis.crypto.randomUUID()}`;
      runCommand(
        reviewDecision === "approve"
          ? t("Approving EBOM review")
          : t("Rejecting EBOM review"),
        (signal) =>
          dataSource.review(
            projectId,
            detail.ebom.globalId,
            selectedRevision.globalId,
            {
              ...common,
              decision: reviewDecision,
              reason: transitionReason || null,
            },
            {
              ...sessionCommandContext,
              idempotencyKey,
              signal,
            },
          ),
      );
    } else if (editor === "release") {
      if (!releaseConfirmed) {
        setFormError(t("Confirm the exact EBOM revision before release."));
        return;
      }
      const idempotencyKey = `ebom-release-${globalThis.crypto.randomUUID()}`;
      runCommand(t("Releasing exact EBOM revision"), (signal) =>
        dataSource.release(
          projectId,
          detail.ebom.globalId,
          selectedRevision.globalId,
          {
            ...common,
            confirmed: true,
            confirmationIntent: "release_exact_ebom_revision",
          },
          {
            ...sessionCommandContext,
            idempotencyKey,
            signal,
          },
        ),
      );
    }
  };

  const compareRevisions = (): void => {
    if (
      !dataSource ||
      !detail ||
      !comparisonSelection.fromRevisionId ||
      !comparisonSelection.toRevisionId ||
      comparisonSelection.fromRevisionId === comparisonSelection.toRevisionId
    ) {
      setFormError(t("Select two different exact revisions to compare."));
      return;
    }
    const controller = new AbortController();
    setFormError(null);
    setComparisonState({ kind: "loading" });
    void dataSource
      .compare(
        projectId,
        detail.ebom.globalId,
        comparisonSelection.fromRevisionId,
        comparisonSelection.toRevisionId,
        controller.signal,
      )
      .then((value) => {
        if (!controller.signal.aborted)
          setComparisonState({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof EngineeringBomRequestCancelledError
        )
          return;
        setComparisonState({
          failure: toRequestFailure(error),
          kind: "failed",
        });
      });
  };

  if (!dataSource) {
    return (
      <section className="workspace-resource-state" role="status">
        <SemanticStatus label={t("Unavailable")} tone="warning" />
        <p>{t("The live EBOM data source is not configured.")}</p>
      </section>
    );
  }
  if (listState.kind === "loading")
    return <LoadingSurface label={t("Loading project EBOM workspace")} />;
  if (listState.kind === "failed") {
    return (
      <FailureSurface
        failure={listState.failure}
        retry={() => {
          setListState({ kind: "loading" });
          setListAttempt((current) => current + 1);
        }}
      />
    );
  }

  const canCreate =
    listState.value.permissions.create &&
    listState.value.policies.length > 0 &&
    sessionCommandContext !== null;
  const editorPolicy = selectedPolicy(listState.value.policies, policyRef);

  return (
    <section
      aria-label={t("Project EBOM workspace")}
      className="ebom-workspace"
    >
      <header className="ebom-workspace__toolbar">
        <div>
          <h2 className="ebom-workspace__title">
            {t("EBOM working revisions")}
          </h2>
          <span className="ebom-workspace__summary">
            {t("NPI-owned working structures")}:{" "}
            {formatNumber(locale, listState.value.items.length, 0)}
          </span>
        </div>
        <div className="detail-actions">
          <Button
            disabled={!canCreate || commandProcessing || editor !== null}
            icon="add"
            onClick={(event) => {
              startEditor("create", event.currentTarget);
            }}
            visual={
              canCreate &&
              editor === null &&
              selectedRevision?.lifecycle.state !== "released"
                ? "primary"
                : "secondary"
            }
          >
            {t("Create EBOM")}
          </Button>
          <Button disabled={commandProcessing} icon="refresh" onClick={reload}>
            {t("Reload")}
          </Button>
        </div>
      </header>
      <div className="scenario-banner scenario-banner--partial" role="status">
        <SemanticStatus label={t("Working structure")} tone="info" />
        <span>
          {t(
            "This workspace does not create formal ERPNext Items, MBOMs, routings or production execution.",
          )}
        </span>
      </div>
      {!listState.value.permissions.create ? (
        <div
          className="scenario-banner scenario-banner--read_only"
          role="status"
        >
          <SemanticStatus label={t("Read only")} tone="info" />
          <span>
            {t("You can inspect EBOM history but cannot create or change it.")}
          </span>
        </div>
      ) : null}
      {listState.value.policies.length === 0 ? (
        <div className="scenario-banner scenario-banner--partial" role="status">
          <SemanticStatus label={t("Unavailable")} tone="warning" />
          <span>
            {t(
              "EBOM creation is unavailable because no accepted synthetic EBOM policy is published.",
            )}
          </span>
        </div>
      ) : null}
      <CommandStatus
        retry={() => {
          if (
            commandState.kind === "failed" &&
            commandState.failure.problem?.status === 409
          )
            reload();
          else latestCommand.current?.();
        }}
        state={commandState}
      />

      {listState.value.items.length === 0 ? (
        <Panel title={t("No EBOM working structure")}>
          <p>
            {t(
              "Create the first EBOM under an exact published synthetic policy.",
            )}
          </p>
          <Button
            disabled={!canCreate || commandProcessing}
            icon="add"
            onClick={(event) => {
              startEditor("create", event.currentTarget);
            }}
          >
            {t("Create EBOM")}
          </Button>
        </Panel>
      ) : (
        <div className="ebom-workspace__layout">
          <Panel scrollableBody title={t("EBOM structures")}>
            <table className="data-table data-table--compact">
              <thead>
                <tr>
                  <th>{t("EBOM key")}</th>
                  <th>{t("Title")}</th>
                  <th>{t("Latest revision")}</th>
                </tr>
              </thead>
              <tbody>
                {listState.value.items.map((item) => (
                  <tr
                    aria-selected={item.globalId === selectedEbomId}
                    className={
                      item.globalId === selectedEbomId
                        ? "is-selected"
                        : undefined
                    }
                    key={item.globalId}
                  >
                    <td>
                      <button
                        className="table-link"
                        data-language-exempt="identifier"
                        onClick={(event) => {
                          returnFocus.current = event.currentTarget;
                          closeEditor();
                          setDetailState({ kind: "loading" });
                          setSelectedEbomId(item.globalId);
                        }}
                        type="button"
                      >
                        {item.engineeringBomKey}
                      </button>
                    </td>
                    <td data-language-exempt="business-data">{item.title}</td>
                    <td data-language-exempt="identifier">
                      {item.latestRevision
                        ? `R${String(item.latestRevision.revisionNumber)}`
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          {detailState.kind === "loading" || detailState.kind === "idle" ? (
            <LoadingSurface label={t("Loading exact EBOM revisions")} />
          ) : detailState.kind === "failed" ? (
            <FailureSurface
              failure={detailState.failure}
              retry={() => {
                setDetailState({ kind: "loading" });
                setDetailAttempt((current) => current + 1);
              }}
            />
          ) : (
            <>
              <div className="ebom-workspace__center">
                <Panel scrollableBody title={t("Immutable revisions")}>
                  <div className="ebom-workspace__revision-toolbar">
                    <div className="detail-actions">
                      <Button
                        disabled={
                          !selectedRevision?.capabilities.revise ||
                          sessionCommandContext === null ||
                          commandProcessing
                        }
                        icon="add"
                        onClick={(event) => {
                          startEditor("revise", event.currentTarget);
                        }}
                      >
                        {t("Create successor revision")}
                      </Button>
                      <Button
                        disabled={detailState.value.revisions.length < 2}
                        icon="analysis"
                        onClick={(event) => {
                          startEditor("compare", event.currentTarget);
                        }}
                      >
                        {t("Compare revisions")}
                      </Button>
                    </div>
                  </div>
                  <table className="data-table data-table--compact">
                    <thead>
                      <tr>
                        <th>{t("Revision")}</th>
                        <th>{t("State")}</th>
                        <th>{t("Lines")}</th>
                        <th>{t("Reason")}</th>
                        <th>{t("Created")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detailState.value.revisions.map((revision) => (
                        <tr
                          aria-selected={
                            revision.globalId === selectedRevision?.globalId
                          }
                          className={
                            revision.globalId === selectedRevision?.globalId
                              ? "is-selected"
                              : undefined
                          }
                          key={revision.globalId}
                        >
                          <td>
                            <button
                              className="table-link"
                              data-language-exempt="identifier"
                              onClick={(event) => {
                                returnFocus.current = event.currentTarget;
                                closeEditor();
                                setSelectedRevisionId(revision.globalId);
                              }}
                              type="button"
                            >
                              {`R${formatNumber(locale, revision.revisionNumber, 0)}`}
                            </button>
                            <small data-language-exempt="identifier">
                              {revision.globalId}
                            </small>
                          </td>
                          <td>
                            <SemanticStatus
                              label={lifecycleLabel(
                                t,
                                revision.lifecycle.state,
                              )}
                              tone={
                                revision.lifecycle.state === "released" ||
                                revision.lifecycle.state === "approved"
                                  ? "success"
                                  : "info"
                              }
                            />
                          </td>
                          <td>
                            {formatNumber(locale, revision.lines.length, 0)}
                          </td>
                          <td data-language-exempt="business-data">
                            {revision.reason}
                          </td>
                          <td>{formatDateTime(locale, revision.createdAt)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Panel>
                {selectedRevision ? (
                  <>
                    <Panel scrollableBody title={t("Exact revision lines")}>
                      <table className="data-table data-table--compact ebom-line-table">
                        <thead>
                          <tr>
                            <th>{t("Line key")}</th>
                            <th>{t("Parent line")}</th>
                            <th>{t("Engineering item")}</th>
                            <th>{t("Description")}</th>
                            <th>{t("Quantity")}</th>
                            <th>{t("Engineering UOM")}</th>
                            <th>{t("Alternate")}</th>
                            <th>{t("Effectivity")}</th>
                            <th>{t("Attributes")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {selectedRevision.lines.map((line) => (
                            <tr key={line.globalId}>
                              <td data-language-exempt="identifier">
                                {line.lineKey}
                              </td>
                              <td data-language-exempt="identifier">
                                {line.parentLineKey ?? "—"}
                              </td>
                              <td data-language-exempt="identifier">
                                {line.engineeringItemId}
                              </td>
                              <td data-language-exempt="business-data">
                                {line.description}
                              </td>
                              <td>
                                {formatDecimal(locale, line.quantity)}{" "}
                                <span data-language-exempt="unit">
                                  {line.engineeringUom}
                                </span>
                              </td>
                              <td data-language-exempt="unit">
                                {line.engineeringUom}
                              </td>
                              <td data-language-exempt="identifier">
                                {line.alternateForLineKey ??
                                  line.alternateGroupKey ??
                                  "—"}
                              </td>
                              <td>
                                {line.effectivityStart
                                  ? formatDate(locale, line.effectivityStart)
                                  : "—"}
                                {line.effectivityEnd
                                  ? ` → ${formatDate(locale, line.effectivityEnd)}`
                                  : ""}
                              </td>
                              <td>
                                {Object.entries(line.attributes).length ? (
                                  <dl className="ebom-attributes">
                                    {Object.entries(line.attributes).map(
                                      ([key, value]) => (
                                        <div
                                          className="ebom-attributes__entry"
                                          key={key}
                                        >
                                          <dt
                                            className="ebom-attributes__key"
                                            data-language-exempt="identifier"
                                          >
                                            {key}
                                          </dt>
                                          <dd
                                            className="ebom-attributes__value"
                                            data-language-exempt="business-data"
                                          >
                                            {value}
                                          </dd>
                                        </div>
                                      ),
                                    )}
                                  </dl>
                                ) : (
                                  "—"
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </Panel>
                    <EngineeringBomPublishRequestWorkspace
                      dataSource={publishRequestDataSource}
                      disabled={commandProcessing || editor !== null}
                      ebom={detailState.value.ebom}
                      itemPublishDataSource={itemPublishDataSource}
                      key={selectedRevision.globalId}
                      onDirtyChange={setPublishDirty}
                      projectId={projectId}
                      revision={selectedRevision}
                    />
                  </>
                ) : null}
              </div>
              <DockedInspector title={t("EBOM inspector")}>
                {selectedRevision ? (
                  <>
                    <SemanticStatus
                      label={lifecycleLabel(
                        t,
                        selectedRevision.lifecycle.state,
                      )}
                      tone={
                        selectedRevision.lifecycle.state === "released" ||
                        selectedRevision.lifecycle.state === "approved"
                          ? "success"
                          : "info"
                      }
                    />
                    <DefinitionList
                      rows={[
                        {
                          label: t("EBOM key"),
                          value: detailState.value.ebom.engineeringBomKey,
                          exempt: "identifier",
                        },
                        {
                          label: t("Revision"),
                          value: `R${String(selectedRevision.revisionNumber)}`,
                          exempt: "identifier",
                        },
                        {
                          label: t("Lifecycle version"),
                          value: formatNumber(
                            locale,
                            selectedRevision.lifecycle.version,
                            0,
                          ),
                        },
                        {
                          label: t("Snapshot hash"),
                          value: selectedRevision.snapshotHash,
                          exempt: "identifier",
                        },
                        {
                          label: t("Policy"),
                          value: detailState.value.policy.title,
                          exempt: "business-data",
                        },
                        {
                          label: t("Created by"),
                          value: selectedRevision.createdByUserId,
                          exempt: "business-data",
                        },
                      ]}
                    />
                    <div className="detail-actions detail-actions--vertical">
                      <Button
                        disabled={
                          !selectedRevision.capabilities.submitReview ||
                          sessionCommandContext === null ||
                          commandProcessing
                        }
                        onClick={(event) => {
                          startEditor("submit", event.currentTarget);
                        }}
                      >
                        {t("Submit for review")}
                      </Button>
                      <Button
                        disabled={
                          !selectedRevision.capabilities.review ||
                          sessionCommandContext === null ||
                          commandProcessing
                        }
                        onClick={(event) => {
                          startEditor("review", event.currentTarget);
                        }}
                      >
                        {t("Record review decision")}
                      </Button>
                      <Button
                        disabled={
                          !selectedRevision.capabilities.release ||
                          sessionCommandContext === null ||
                          commandProcessing
                        }
                        onClick={(event) => {
                          startEditor("release", event.currentTarget);
                        }}
                      >
                        {t("Release revision")}
                      </Button>
                    </div>
                    <Panel scrollableBody title={t("Lifecycle events")}>
                      {selectedRevision.events.length ? (
                        <ol className="ebom-events">
                          {selectedRevision.events.map((event) => (
                            <li
                              className="ebom-events__entry"
                              key={event.globalId}
                            >
                              <strong>
                                {lifecycleLabel(t, event.fromState)} →{" "}
                                {lifecycleLabel(t, event.toState)}
                              </strong>
                              <span className="ebom-events__time">
                                {formatDateTime(locale, event.occurredAt)}
                              </span>
                              <small
                                className="ebom-events__actor"
                                data-language-exempt="business-data"
                              >
                                {event.actorUserId}
                              </small>
                            </li>
                          ))}
                        </ol>
                      ) : (
                        <p>{t("No lifecycle event has been recorded.")}</p>
                      )}
                    </Panel>
                  </>
                ) : null}
              </DockedInspector>
            </>
          )}
        </div>
      )}

      {(editor === "create" || editor === "revise") && list ? (
        <Panel
          title={
            editor === "create"
              ? t("Create EBOM working structure")
              : t("Create immutable successor revision")
          }
        >
          <form
            className="ebom-form"
            onSubmit={(event) => {
              event.preventDefault();
              submitContent();
            }}
          >
            {editor === "create" ? (
              <>
                <label
                  ref={(element) => {
                    firstEditorControl.current = element;
                  }}
                >
                  <span>{t("Exact EBOM policy")}</span>
                  <Select
                    onChange={(event) => {
                      setPolicyRef(event.currentTarget.value);
                      setEditorTouched(true);
                    }}
                    required
                    value={policyRef}
                  >
                    {list.policies.map((policy) => (
                      <option
                        data-language-exempt="business-data"
                        key={policyValue(policy)}
                        value={policyValue(policy)}
                      >
                        {policy.title} · v{String(policy.version)}
                      </option>
                    ))}
                  </Select>
                </label>
                <label>
                  <span>{t("EBOM key")}</span>
                  <TextInput
                    maxLength={64}
                    onChange={(event) => {
                      setEngineeringBomKey(event.currentTarget.value);
                      setEditorTouched(true);
                    }}
                    required
                    value={engineeringBomKey}
                  />
                </label>
                <label>
                  <span>{t("Title")}</span>
                  <TextInput
                    maxLength={140}
                    onChange={(event) => {
                      setTitle(event.currentTarget.value);
                      setEditorTouched(true);
                    }}
                    required
                    value={title}
                  />
                </label>
              </>
            ) : null}
            <label
              ref={(element) => {
                if (editor === "revise") firstEditorControl.current = element;
              }}
            >
              <span>{t("Revision reason")}</span>
              <TextInput
                maxLength={280}
                onChange={(event) => {
                  setRevisionForm({
                    ...revisionForm,
                    reason: event.currentTarget.value,
                  });
                  setEditorTouched(true);
                }}
                required
                value={revisionForm.reason}
              />
            </label>
            <label>
              <span>{t("Effectivity note")}</span>
              <TextInput
                maxLength={280}
                onChange={(event) => {
                  setRevisionForm({
                    ...revisionForm,
                    effectivityNote: event.currentTarget.value,
                  });
                  setEditorTouched(true);
                }}
                value={revisionForm.effectivityNote}
              />
            </label>
            {editorPolicy ? (
              <LineEditor
                lines={revisionForm.lines}
                maximumNodes={editorPolicy.maximumNodes}
                onChange={(lines) => {
                  setRevisionForm({ ...revisionForm, lines });
                  setEditorTouched(true);
                }}
                policy={editorPolicy}
              />
            ) : null}
            {formError ? (
              <p className="ebom-form__wide form-error" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="detail-actions ebom-form__wide">
              <Button
                disabled={
                  commandProcessing ||
                  sessionCommandContext === null ||
                  editorPolicy === null
                }
                type="submit"
                visual="primary"
              >
                {editor === "create" ? t("Create EBOM") : t("Create revision")}
              </Button>
              <Button
                disabled={commandProcessing || sessionCommandContext === null}
                onClick={closeEditor}
                type="button"
              >
                {t("Cancel")}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}

      {(editor === "submit" || editor === "review" || editor === "release") &&
      selectedRevision ? (
        <Panel title={t("EBOM lifecycle review")}>
          <form
            className="ebom-form ebom-form--transition"
            onSubmit={(event) => {
              event.preventDefault();
              submitTransition();
            }}
          >
            <div
              className="ebom-form__wide scenario-banner scenario-banner--partial"
              role="status"
            >
              <SemanticStatus label={t("Exact revision")} tone="info" />
              <span>
                {t(
                  "This action applies only to EBOM revision {{revision}} with {{lines}} immutable lines.",
                  {
                    revision: `R${String(selectedRevision.revisionNumber)}`,
                    lines: formatNumber(
                      locale,
                      selectedRevision.lines.length,
                      0,
                    ),
                  },
                )}
              </span>
              <code data-language-exempt="identifier">
                SHA-256 {selectedRevision.snapshotHash}
              </code>
            </div>
            {editor === "review" ? (
              <label
                ref={(element) => {
                  firstEditorControl.current = element;
                }}
              >
                <span>{t("Review decision")}</span>
                <Select
                  onChange={(event) => {
                    setReviewDecision(
                      event.currentTarget.value as "approve" | "reject",
                    );
                    setEditorTouched(true);
                  }}
                  value={reviewDecision}
                >
                  <option value="approve">{t("Approve")}</option>
                  <option value="reject">{t("Reject")}</option>
                </Select>
              </label>
            ) : editor === "release" ? (
              <label
                className="confirmation-check ebom-form__wide"
                ref={(element) => {
                  firstEditorControl.current = element;
                }}
              >
                <input
                  checked={releaseConfirmed}
                  onChange={(event) => {
                    setReleaseConfirmed(event.currentTarget.checked);
                    setEditorTouched(true);
                  }}
                  type="checkbox"
                />
                <span>
                  {t(
                    "I confirm release of this exact immutable EBOM revision. No ERPNext execution will occur.",
                  )}
                </span>
              </label>
            ) : null}
            {editor !== "release" ? (
              <label
                ref={(element) => {
                  if (editor === "submit") firstEditorControl.current = element;
                }}
              >
                <span>{t("Reason")}</span>
                <TextInput
                  maxLength={280}
                  onChange={(event) => {
                    setTransitionReason(event.currentTarget.value);
                    setEditorTouched(true);
                  }}
                  required={editor === "review" && reviewDecision === "reject"}
                  value={transitionReason}
                />
              </label>
            ) : null}
            {formError ? (
              <p className="ebom-form__wide form-error" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="detail-actions ebom-form__wide">
              <Button
                disabled={commandProcessing}
                type="submit"
                visual={editor === "release" ? "danger" : "primary"}
              >
                {editor === "submit"
                  ? t("Submit for review")
                  : editor === "review"
                    ? t("Record decision")
                    : t("Release exact revision")}
              </Button>
              <Button
                disabled={commandProcessing}
                onClick={closeEditor}
                type="button"
              >
                {t("Cancel")}
              </Button>
            </div>
          </form>
        </Panel>
      ) : null}

      {editor === "compare" && detail ? (
        <Panel title={t("Compare exact EBOM revisions")}>
          <form
            className="ebom-form ebom-form--compare"
            onSubmit={(event) => {
              event.preventDefault();
              compareRevisions();
            }}
          >
            <label
              ref={(element) => {
                firstEditorControl.current = element;
              }}
            >
              <span>{t("From revision")}</span>
              <Select
                onChange={(event) => {
                  setComparisonSelection({
                    ...comparisonSelection,
                    fromRevisionId: event.currentTarget.value,
                  });
                  setComparisonState({ kind: "idle" });
                }}
                required
                value={comparisonSelection.fromRevisionId}
              >
                {detail.revisions.map((revision) => (
                  <option
                    data-language-exempt="identifier"
                    key={revision.globalId}
                    value={revision.globalId}
                  >
                    {`R${String(revision.revisionNumber)}`}
                  </option>
                ))}
              </Select>
            </label>
            <label>
              <span>{t("To revision")}</span>
              <Select
                onChange={(event) => {
                  setComparisonSelection({
                    ...comparisonSelection,
                    toRevisionId: event.currentTarget.value,
                  });
                  setComparisonState({ kind: "idle" });
                }}
                required
                value={comparisonSelection.toRevisionId}
              >
                {detail.revisions.map((revision) => (
                  <option
                    data-language-exempt="identifier"
                    key={revision.globalId}
                    value={revision.globalId}
                  >
                    {`R${String(revision.revisionNumber)}`}
                  </option>
                ))}
              </Select>
            </label>
            {formError ? (
              <p className="ebom-form__wide form-error" role="alert">
                {formError}
              </p>
            ) : null}
            <div className="detail-actions ebom-form__wide">
              <Button type="submit" visual="primary">
                {t("Compare revisions")}
              </Button>
              <Button onClick={closeEditor} type="button">
                {t("Close")}
              </Button>
            </div>
          </form>
          {comparisonState.kind === "loading" ? (
            <LoadingSurface label={t("Comparing exact EBOM revisions")} />
          ) : comparisonState.kind === "failed" ? (
            <FailureSurface
              failure={comparisonState.failure}
              retry={compareRevisions}
            />
          ) : comparisonState.kind === "loaded" ? (
            <div className="ebom-comparison">
              <div className="ebom-comparison__summary">
                <SemanticStatus
                  label={
                    comparisonState.value.identical
                      ? t("Identical revisions")
                      : t("Differences found")
                  }
                  tone={comparisonState.value.identical ? "success" : "warning"}
                />
                {(
                  [
                    "added",
                    "removed",
                    "quantity",
                    "substitution",
                    "attribute",
                  ] as const
                ).map((changeType) => (
                  <span key={changeType}>
                    {changeTypeLabel(t, changeType)}:{" "}
                    {formatNumber(
                      locale,
                      comparisonState.value.summary[changeType],
                      0,
                    )}
                  </span>
                ))}
              </div>
              {comparisonState.value.identical ? (
                <p>
                  {t("The selected exact revisions have no line differences.")}
                </p>
              ) : (
                <table className="data-table data-table--compact">
                  <thead>
                    <tr>
                      <th>{t("Line key")}</th>
                      <th>{t("Change type")}</th>
                      <th>{t("Changed fields")}</th>
                      <th>{t("Before")}</th>
                      <th>{t("After")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparisonState.value.changes.map((change) => (
                      <tr key={change.lineKey}>
                        <td data-language-exempt="identifier">
                          {change.lineKey}
                        </td>
                        <td>
                          <SemanticStatus
                            label={changeTypeLabel(t, change.changeType)}
                            tone={
                              change.changeType === "removed"
                                ? "warning"
                                : "info"
                            }
                          />
                        </td>
                        <td data-language-exempt="identifier">
                          {change.changedFields.join(", ")}
                        </td>
                        <td data-language-exempt="business-data">
                          {change.before
                            ? `${change.before.engineeringItemId} · ${change.before.quantity} ${change.before.engineeringUom}`
                            : "—"}
                        </td>
                        <td data-language-exempt="business-data">
                          {change.after
                            ? `${change.after.engineeringItemId} · ${change.after.quantity} ${change.after.engineeringUom}`
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ) : null}
        </Panel>
      ) : null}
    </section>
  );
}
