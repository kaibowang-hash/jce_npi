import { useEffect, useRef, useState } from "react";
import type {
  ProjectSetupDataSource,
  SetupDrafts,
} from "../api/project-setup-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { ReportWorkspaceDirty } from "../app/workspace-navigation";
import { RequestFailurePanel } from "../components/problem-details-panel";
import { SemanticStatus } from "../components/primitives";
import { useI18n } from "../i18n/runtime";
import { Button, TextInput } from "../ui-adapters/npi-ui";

export function ProjectRoleDefinitions({
  roleKeys,
}: {
  roleKeys: readonly string[];
}): React.JSX.Element {
  const { t } = useI18n();
  const definitions = [
    {
      key: "engineering",
      label: t("Engineering"),
      responsibilities: t(
        "Feasibility, DFM, tooling, trials, process instructions and technical handover",
      ),
      stages: "G0–G7",
    },
    {
      key: "quality",
      label: t("Quality"),
      responsibilities: t(
        "Inspection planning, sample validation, defect evidence and quality controls",
      ),
      stages: "G0–G7",
    },
    {
      key: "purchasing",
      label: t("Purchasing"),
      responsibilities: t(
        "Supplier capacity, external services, purchasing and material arrival",
      ),
      stages: "G1, G3, G4, G6, G7",
    },
    {
      key: "sales",
      label: t("Sales"),
      responsibilities: t(
        "Customer requirements, sample feedback, approval evidence and delivery commitments",
      ),
      stages: "G0, G1, G2, G5, G6, G7",
    },
    {
      key: "warehouse",
      label: t("Warehouse"),
      responsibilities: t(
        "Receiving, lot identification, storage, traceability and packaging",
      ),
      stages: "G4, G6, G7",
    },
    {
      key: "materials_control",
      label: t("Materials control"),
      responsibilities: t(
        "Material demand, arrival coordination, pilot supply and shortage follow-up",
      ),
      stages: "G1, G3, G4, G6, G7",
    },
  ];
  return (
    <div className="project-setup-grid">
      <table className="data-table data-table--compact">
        <thead>
          <tr>
            <th>{t("Role")}</th>
            <th>{t("Suggested responsibilities")}</th>
            <th>{t("Gates")}</th>
          </tr>
        </thead>
        <tbody>
          {roleKeys.map((key) => {
            const item = definitions.find((value) => value.key === key);
            return (
              <tr key={key}>
                <td>
                  {item ? (
                    item.label
                  ) : (
                    <span data-language-exempt="identifier">{key}</span>
                  )}
                </td>
                <td>
                  {item?.responsibilities ??
                    t("Defined by the published work policy")}
                </td>
                <td data-language-exempt="identifier">{item?.stages ?? "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function InjectionTemplateDraft({
  dataSource,
  projectId,
  projectVersion,
  reportWorkspaceDirty,
}: {
  dataSource: ProjectSetupDataSource;
  projectId: string;
  projectVersion: number;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
}): React.JSX.Element {
  const { t, sessionCommandContext } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<RequestFailure | null>(null);
  const [result, setResult] = useState<SetupDrafts | null>(null);
  const [operation, setOperation] = useState<{
    command: {
      expectedProjectVersion: number;
      templateCode: string;
      title: string;
    };
    idempotencyKey: string;
  } | null>(null);
  const controller = useRef<AbortController | null>(null);
  const lock = useRef(false);
  const trigger = useRef<HTMLDivElement>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (!reportWorkspaceDirty) return;
    reportWorkspaceDirty(
      !result && (code || title || pending)
        ? {
            objectIdentity: `${projectId}:template-draft`,
            version: String(projectVersion),
            returnFocusTarget: () =>
              trigger.current?.querySelector<HTMLElement>(
                "ix-button, button",
              ) ?? null,
          }
        : null,
    );
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [
    code,
    expanded,
    pending,
    projectId,
    projectVersion,
    reportWorkspaceDirty,
    result,
    title,
  ]);
  async function submit(): Promise<void> {
    if (lock.current || !sessionCommandContext) return;
    lock.current = true;
    setPending(true);
    setFailure(null);
    const current = operation ?? {
      command: {
        expectedProjectVersion: projectVersion,
        templateCode: code.trim(),
        title: title.trim(),
      },
      idempotencyKey: `template-draft-${crypto.randomUUID()}`,
    };
    setOperation(current);
    const abort = new AbortController();
    controller.current = abort;
    try {
      const value = await dataSource.createDrafts(projectId, current.command, {
        csrfToken: sessionCommandContext.csrfToken,
        idempotencyKey: current.idempotencyKey,
        signal: abort.signal,
      });
      if (!abort.signal.aborted) setResult(value);
    } catch (error: unknown) {
      if (!abort.signal.aborted) setFailure(toRequestFailure(error));
    } finally {
      if (!abort.signal.aborted) {
        lock.current = false;
        setPending(false);
      }
    }
  }
  return (
    <div className="project-setup-template" ref={trigger}>
      <Button
        type="button"
        disabled={pending}
        onClick={() => {
          setExpanded((value) => !value);
        }}
      >
        {t("Injection-moulding collaboration template")}
      </Button>
      {expanded ? (
        <>
          <p>
            {t(
              "Creates an unpublished new-tool Project template and work policy for Engineering, Quality, Purchasing, Sales, Warehouse and Materials Control.",
            )}
          </p>
          <ol>
            {[
              t("Customer requirements and opportunity review"),
              t("Feasibility and project authorization"),
              t("Product design and DFM baseline"),
              t("Tooling design and manufacturing authorization"),
              t("Tooling completion and trial readiness"),
              t("Trial validation and sample approval review"),
              t("NPI and pilot production readiness"),
              t("Production handover and launch review"),
            ].map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ol>
          <ProjectRoleDefinitions
            roleKeys={[
              "engineering",
              "quality",
              "purchasing",
              "sales",
              "warehouse",
              "materials_control",
            ]}
          />
          <p>
            {t(
              "Review the draft in administration, configure Gate evidence and approval requirements, then publish the versions. Existing Projects keep their original Gate snapshots.",
            )}
          </p>
          {result ? (
            <div role="status">
              <SemanticStatus
                label={t("Template drafts created")}
                tone="success"
              />
              <div className="project-setup-toolbar">
                <a
                  className="table-link"
                  href={`/app/npi-project-template-version/${encodeURIComponent(`${result.templateGlobalId}:1`)}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("Review project template draft")}
                </a>
                <a
                  className="table-link"
                  href={`/app/npi-project-work-policy-version/${encodeURIComponent(`${result.policyGlobalId}:1`)}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t("Review work policy draft")}
                </a>
              </div>
            </div>
          ) : (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void submit();
              }}
            >
              <fieldset disabled={pending || operation !== null}>
                <label>
                  <span>{t("Template code")}</span>
                  <TextInput
                    required
                    maxLength={64}
                    pattern="[A-Za-z0-9][A-Za-z0-9._/-]*"
                    value={code}
                    onChange={(e) => {
                      setCode(e.currentTarget.value);
                    }}
                  />
                </label>
                <label>
                  <span>{t("Template title")}</span>
                  <TextInput
                    required
                    maxLength={140}
                    value={title}
                    onChange={(e) => {
                      setTitle(e.currentTarget.value);
                    }}
                  />
                </label>
              </fieldset>
              <Button
                disabled={
                  pending ||
                  !sessionCommandContext ||
                  (operation !== null && !failure)
                }
                type="submit"
              >
                {operation
                  ? t("Retry exact draft creation")
                  : t("Create template drafts")}
              </Button>
              {pending ? (
                <p role="status" aria-busy="true">
                  {t("Creating template drafts")}
                </p>
              ) : null}
              {failure ? (
                <div role="alert">
                  <RequestFailurePanel failure={failure} />
                  {failure.kind === "problem" && !failure.problem?.retryable ? (
                    <Button
                      type="button"
                      onClick={() => {
                        setOperation(null);
                        setFailure(null);
                      }}
                    >
                      {t("Edit inputs")}
                    </Button>
                  ) : null}
                </div>
              ) : null}
            </form>
          )}
        </>
      ) : null}
    </div>
  );
}
