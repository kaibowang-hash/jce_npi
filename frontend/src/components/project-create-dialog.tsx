import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import {
  ProjectRequestCancelledError,
  type ProjectCreationContext,
  type ProjectCreationDataSource,
} from "../api/project-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { ProjectType } from "../domain/view-models";
import { useI18n } from "../i18n/runtime";
import { Button, focusControl, Select, TextInput } from "../ui-adapters/npi-ui";
import { RequestFailurePanel } from "./problem-details-panel";
import { ERPMasterSelect } from "./erp-master-select";

type LoadState =
  | { kind: "loading" }
  | { kind: "failed"; failure: RequestFailure }
  | { kind: "ready"; context: ProjectCreationContext };

function typeLabel(
  type: ProjectType,
  t: ReturnType<typeof useI18n>["t"],
): string {
  if (type === "customer_owned_tool") return t("Customer-owned tool project");
  if (type === "tool_change") return t("Tool change project");
  return t("New tool project");
}

function defaultTargetSop(): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + 90);
  return date.toISOString().slice(0, 10);
}

export function ProjectCreateDialog({
  dataSource,
  navigate,
  onClose,
}: {
  dataSource: ProjectCreationDataSource;
  navigate: (target: string) => void;
  onClose: () => void;
}): React.JSX.Element {
  const { sessionCommandContext, t } = useI18n();
  const [loadState, setLoadState] = useState<LoadState>({ kind: "loading" });
  const [businessCode, setBusinessCode] = useState("");
  const [customerSourceKey, setCustomerSourceKey] = useState("");
  const [title, setTitle] = useState("");
  const [targetSop, setTargetSop] = useState(defaultTargetSop);
  const [templateKey, setTemplateKey] = useState("");
  const [projectType, setProjectType] = useState<ProjectType>("new_tool");
  const [submitting, setSubmitting] = useState(false);
  const [failure, setFailure] = useState<RequestFailure | null>(null);
  const headingId = useId();
  const submittingRef = useRef(false);
  const idempotencyKey = useRef(globalThis.crypto.randomUUID());
  const request = useRef<AbortController | null>(null);
  const initialFieldFocused = useRef(false);
  const dialog = useRef<HTMLDivElement | null>(null);
  const heading = useRef<HTMLHeadingElement | null>(null);
  const businessCodeInput = useRef<HTMLInputElement | null>(null);

  const load = useCallback((): void => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    initialFieldFocused.current = false;
    setLoadState({ kind: "loading" });
    void dataSource
      .loadCreationContext(controller.signal)
      .then((context) => {
        if (controller.signal.aborted) return;
        setLoadState({ context, kind: "ready" });
        const template = context.templates[0];
        if (template) {
          setTemplateKey(`${template.globalId}:${String(template.version)}`);
          setProjectType(template.applicableProjectTypes[0] ?? "new_tool");
        }
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ProjectRequestCancelledError
        )
          return;
        setLoadState({ failure: toRequestFailure(error), kind: "failed" });
      });
  }, [dataSource]);

  useEffect(() => {
    const root = document.querySelector<HTMLElement>("#root");
    if (root) root.inert = true;
    void focusControl(heading.current);
    const focusableSelector =
      'ix-button:not([disabled]), button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const focusable = (): HTMLElement[] => [
      ...(dialog.current?.querySelectorAll<HTMLElement>(focusableSelector) ??
        []),
    ];
    const initialLoad = window.setTimeout(load, 0);
    const handleKey = (event: KeyboardEvent): void => {
      if (event.key === "Escape" && !submittingRef.current) onClose();
      if (event.key === "Tab") {
        const controls = focusable();
        const first = controls[0];
        const last = controls.at(-1);
        if (!first || !last) return;
        if (
          event.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === heading.current)
        ) {
          event.preventDefault();
          void focusControl(last);
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          void focusControl(first);
        }
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => {
      window.clearTimeout(initialLoad);
      request.current?.abort();
      document.removeEventListener("keydown", handleKey);
      if (root) root.inert = false;
    };
  }, [load, onClose]);

  const selectedTemplate = useMemo(
    () =>
      loadState.kind === "ready"
        ? (loadState.context.templates.find(
            (template) =>
              `${template.globalId}:${String(template.version)}` ===
              templateKey,
          ) ?? null)
        : null,
    [loadState, templateKey],
  );
  const requiresReferences = Boolean(
    selectedTemplate?.referenceRules.some(
      (rule) => rule.required && rule.type !== "customer",
    ),
  );
  useEffect(() => {
    if (!selectedTemplate || initialFieldFocused.current) return;
    initialFieldFocused.current = true;
    void focusControl(businessCodeInput.current);
  }, [selectedTemplate]);
  const canSubmit = Boolean(
    sessionCommandContext &&
    selectedTemplate &&
    !requiresReferences &&
    (!selectedTemplate.referenceRules.some(
      (rule) => rule.type === "customer" && rule.required,
    ) ||
      customerSourceKey) &&
    businessCode.trim() &&
    title.trim() &&
    targetSop &&
    !submitting,
  );

  const changePayload = (): void => {
    idempotencyKey.current = globalThis.crypto.randomUUID();
    setFailure(null);
  };

  const submit = (event: React.FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (
      !canSubmit ||
      !sessionCommandContext ||
      !selectedTemplate ||
      loadState.kind !== "ready"
    )
      return;
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    submittingRef.current = true;
    setSubmitting(true);
    setFailure(null);
    void dataSource
      .create(
        {
          businessCode: businessCode.trim(),
          ...(customerSourceKey &&
          selectedTemplate.referenceRules.some(
            (rule) => rule.type === "customer",
          )
            ? { customerSourceKey }
            : {}),
          expectedVersion: selectedTemplate.expectedVersion,
          projectType,
          targetSop,
          templateGlobalId: selectedTemplate.globalId,
          templateVersion: selectedTemplate.version,
          title: title.trim(),
        },
        loadState.context,
        {
          csrfToken: sessionCommandContext.csrfToken,
          idempotencyKey: idempotencyKey.current,
          signal: controller.signal,
        },
      )
      .then((created) => {
        if (!controller.signal.aborted)
          navigate(`/projects/${created.project.globalId}`);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setFailure(toRequestFailure(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          submittingRef.current = false;
          setSubmitting(false);
        }
      });
  };

  return createPortal(
    <div
      aria-labelledby={headingId}
      aria-modal="true"
      className="impact-review project-create-dialog"
      ref={dialog}
      role="dialog"
    >
      <form className="impact-review__surface" onSubmit={submit}>
        <header className="impact-review__header">
          <h2 id={headingId} ref={heading} tabIndex={-1}>
            {t("Create project")}
          </h2>
        </header>
        <p className="project-create-dialog__message">
          {t("Create a controlled project draft from a published template.")}
        </p>
        {loadState.kind === "loading" ? (
          <p aria-busy="true" className="project-create-dialog__message">
            {t("Loading project creation options")}
          </p>
        ) : loadState.kind === "failed" ? (
          <div className="project-create-dialog__message">
            <RequestFailurePanel failure={loadState.failure} />
            <Button
              className="project-create-dialog__retry"
              icon="refresh"
              onClick={load}
            >
              {t("Retry")}
            </Button>
          </div>
        ) : loadState.context.templates.length === 0 ? (
          <p className="project-create-dialog__message">
            {t("No published project template is available.")}
          </p>
        ) : (
          <div className="project-create-dialog__grid">
            <label className="project-create-dialog__field project-create-dialog__field--wide">
              <span>{t("Business code")}</span>
              <TextInput
                autoComplete="off"
                maxLength={64}
                onChange={(event) => {
                  changePayload();
                  setBusinessCode(event.currentTarget.value);
                }}
                pattern="[A-Za-z0-9][A-Za-z0-9._/-]*"
                ref={businessCodeInput}
                required
                value={businessCode}
              />
            </label>
            <label className="project-create-dialog__field project-create-dialog__field--wide">
              <span>{t("Project title")}</span>
              <TextInput
                maxLength={140}
                onChange={(event) => {
                  changePayload();
                  setTitle(event.currentTarget.value);
                }}
                required
                value={title}
              />
            </label>
            <label className="project-create-dialog__field project-create-dialog__field--wide">
              <span>{t("Project template")}</span>
              <Select
                onChange={(event) => {
                  changePayload();
                  const key = event.currentTarget.value;
                  setTemplateKey(key);
                  const template = loadState.context.templates.find(
                    (candidate) =>
                      `${candidate.globalId}:${String(candidate.version)}` ===
                      key,
                  );
                  setProjectType(
                    template?.applicableProjectTypes[0] ?? "new_tool",
                  );
                }}
                value={templateKey}
              >
                {loadState.context.templates.map((template) => (
                  <option
                    data-language-exempt="business-data"
                    key={`${template.globalId}:${String(template.version)}`}
                    value={`${template.globalId}:${String(template.version)}`}
                  >
                    {template.code} · {template.title} · v{template.version}
                  </option>
                ))}
              </Select>
            </label>
            <label className="project-create-dialog__field">
              <span>{t("Project type")}</span>
              <Select
                onChange={(event) => {
                  changePayload();
                  setProjectType(event.currentTarget.value as ProjectType);
                }}
                value={projectType}
              >
                {(selectedTemplate?.applicableProjectTypes ?? []).map(
                  (type) => (
                    <option key={type} value={type}>
                      {typeLabel(type, t)}
                    </option>
                  ),
                )}
              </Select>
            </label>
            <label className="project-create-dialog__field">
              <span>{t("Target SOP")}</span>
              <TextInput
                onChange={(event) => {
                  changePayload();
                  setTargetSop(event.currentTarget.value);
                }}
                required
                type="date"
                value={targetSop}
              />
            </label>
            {selectedTemplate?.referenceRules.some(
              (rule) => rule.type === "customer",
            ) ? (
              <div className="project-create-dialog__field">
                <span>{t("Customer")}</span>
                <ERPMasterSelect
                  kind="customer"
                  label={t("Customer")}
                  value={customerSourceKey}
                  disabled={submitting}
                  required={selectedTemplate.referenceRules.some(
                    (rule) => rule.type === "customer" && rule.required,
                  )}
                  onChange={(record) => {
                    changePayload();
                    setCustomerSourceKey(record?.sourceKey ?? "");
                  }}
                />
              </div>
            ) : null}
            <div className="project-create-dialog__owner">
              <span>{t("Project owner")}</span>
              <strong
                className="project-create-dialog__owner-value"
                data-language-exempt="business-data"
              >
                {loadState.context.ownerUserId}
              </strong>
            </div>
          </div>
        )}
        {requiresReferences ? (
          <p className="project-create-dialog__message" role="alert">
            {t(
              "This template requires project references and is not available in quick create.",
            )}
          </p>
        ) : null}
        {failure ? (
          <div className="project-create-dialog__message">
            <RequestFailurePanel failure={failure} />
          </div>
        ) : null}
        <footer className="impact-review__footer">
          <Button disabled={submitting} onClick={onClose}>
            {t("Cancel")}
          </Button>
          <Button
            disabled={!canSubmit}
            icon="add"
            type="submit"
            visual="primary"
          >
            {submitting ? t("Creating") : t("Create project")}
          </Button>
        </footer>
      </form>
    </div>,
    document.body,
  );
}
