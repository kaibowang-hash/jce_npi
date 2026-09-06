import { useEffect, useRef, useState } from "react";
import type {
  CreateReadinessTemplateCommand,
  ReadinessDataSource,
  ReadinessTemplateVersion,
  ReadinessItemDefinition,
} from "../api/readiness-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type {
  ReportWorkspaceDirty,
  RequestWorkspaceTransition,
} from "../app/workspace-navigation";
import { RequestFailurePanel } from "../components/problem-details-panel";
import { ImpactReview, Panel, SemanticStatus } from "../components/primitives";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";
import "./project-setup-workspace.css";

type Operation =
  | {
      kind: "save";
      command: CreateReadinessTemplateCommand;
      retained: ReadinessTemplateVersion | null;
      key: string;
    }
  | { kind: "publish"; retained: ReadinessTemplateVersion; key: string };

export function ReadinessTemplateSetup({
  dataSource,
  projectId,
  onClose,
  onPublished,
  reportWorkspaceDirty,
  requestWorkspaceTransition,
}: {
  dataSource: ReadinessDataSource;
  projectId: string;
  onClose: () => void;
  onPublished: () => void;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
  requestWorkspaceTransition?: RequestWorkspaceTransition | undefined;
}): React.JSX.Element {
  const { t, sessionCommandContext } = useI18n();
  const categories = [
    { key: "engineering", title: t("Engineering") },
    { key: "quality", title: t("Quality") },
    { key: "purchasing", title: t("Purchasing") },
    { key: "sales", title: t("Sales") },
    { key: "warehouse", title: t("Warehouse") },
    { key: "materials_control", title: t("Materials control") },
  ];
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [items, setItems] = useState<readonly ReadinessItemDefinition[]>(() => {
    const titles = [
      t("Engineering release and process instructions"),
      t("Inspection plan and sample validation"),
      t("Supplier and purchased material readiness"),
      t("Customer requirements and sample approval evidence"),
      t("Receiving, traceability and packaging readiness"),
      t("Material availability and pilot supply plan"),
    ];
    return categories.map((category, index) => ({
      key: `${category.key}_readiness`,
      categoryKey: category.key,
      title: titles[index] ?? category.title,
      weight: 1,
      required: true,
      blockingLevel: "P0",
      gateKey: "G6",
      completionRule: "exact_evidence",
      applicability: {
        projectTypes: [],
        industryKeys: [],
        customerReferenceKeys: [],
      },
      evidenceRequirements: [
        {
          key: "released_evidence",
          acceptedSourceKinds: ["released_document"],
          minimumCount: 1,
          unavailableBlocks: true,
        },
      ],
    }));
  });
  const [retained, setRetained] = useState<ReadinessTemplateVersion | null>(
    null,
  );
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState(false);
  const [operation, setOperation] = useState<Operation | null>(null);
  const [review, setReview] = useState(false);
  const [failure, setFailure] = useState<RequestFailure | null>(null);
  const controller = useRef<AbortController | null>(null);
  const lock = useRef(false);
  const focus = useRef<HTMLDivElement>(null);
  useEffect(
    () => () => {
      controller.current?.abort();
    },
    [],
  );
  useEffect(() => {
    reportWorkspaceDirty?.(
      dirty || pending
        ? {
            objectIdentity: `${projectId}:readiness-template`,
            version: retained?.snapshotHash ?? "draft",
            returnFocusTarget: () =>
              focus.current?.querySelector<HTMLElement>("ix-button, button") ??
              null,
          }
        : null,
    );
    return () => reportWorkspaceDirty?.(null);
  }, [dirty, pending, projectId, reportWorkspaceDirty, retained]);
  async function execute(value: Operation): Promise<void> {
    if (lock.current || !sessionCommandContext) return;
    lock.current = true;
    setPending(true);
    setFailure(null);
    setOperation(value);
    setReview(false);
    const abort = new AbortController();
    controller.current = abort;
    const request = {
      csrfToken: sessionCommandContext.csrfToken,
      idempotencyKey: value.key,
      signal: abort.signal,
    };
    try {
      const result =
        value.kind === "publish"
          ? await dataSource.publishTemplate(
              value.retained.templateGlobalId,
              value.retained.templateVersion,
              { expectedOptimisticVersion: value.retained.optimisticVersion },
              request,
            )
          : value.retained
            ? await dataSource.editTemplate(
                value.retained.templateGlobalId,
                value.retained.templateVersion,
                {
                  expectedOptimisticVersion: value.retained.optimisticVersion,
                  title: value.command.title,
                  applicability: value.command.applicability,
                  categories: value.command.categories,
                  items: value.command.items,
                },
                request,
              )
            : await dataSource.createTemplate(value.command, request);
      if (abort.signal.aborted) return;
      setRetained(result.template);
      setDirty(false);
      setOperation(null);
      if (value.kind === "publish") onPublished();
    } catch (error: unknown) {
      if (!abort.signal.aborted) setFailure(toRequestFailure(error));
    } finally {
      if (!abort.signal.aborted) {
        lock.current = false;
        setPending(false);
      }
    }
  }
  function save(): void {
    const value: Operation = {
      kind: "save",
      retained,
      key: `readiness-template-${crypto.randomUUID()}`,
      command: {
        templateCode: code.trim(),
        title: title.trim(),
        applicability: {
          projectTypes: ["new_tool"],
          customerReferenceKeys: [],
          industryKeys: [],
        },
        categories,
        items,
      },
    };
    void execute(value);
  }
  function update(key: string, patch: Partial<ReadinessItemDefinition>): void {
    setDirty(true);
    setItems((rows) =>
      rows.map((row) => (row.key === key ? { ...row, ...patch } : row)),
    );
  }
  return (
    <section className="project-setup" ref={focus}>
      <Panel title={t("Configure readiness template")}>
        <p>
          {t(
            "Review this six-department new-tool readiness draft. Each required item needs an exact released document; incomplete P0 items block readiness.",
          )}
        </p>
        <p>
          {t(
            "Gate keys must exist in the Project that uses this template. This setup does not add Gates to existing Projects.",
          )}
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            save();
          }}
        >
          <fieldset disabled={pending || operation !== null}>
            <label>
              <span>{t("Template code")}</span>
              <TextInput
                required
                maxLength={64}
                disabled={retained !== null}
                value={code}
                onChange={(e) => {
                  setDirty(true);
                  setCode(e.currentTarget.value);
                }}
              />
            </label>
            <label>
              <span>{t("Template title")}</span>
              <TextInput
                required
                maxLength={200}
                value={title}
                onChange={(e) => {
                  setDirty(true);
                  setTitle(e.currentTarget.value);
                }}
              />
            </label>
            <div className="project-setup-grid">
              <table className="data-table data-table--compact">
                <thead>
                  <tr>
                    <th>{t("Department")}</th>
                    <th>{t("Readiness item")}</th>
                    <th>{t("Gate key")}</th>
                    <th>{t("Weight")}</th>
                    <th>{t("Blocking level")}</th>
                    <th>{t("Required")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, index) => (
                    <tr key={item.key}>
                      <td>{categories[index]?.title}</td>
                      <td>
                        <TextInput
                          aria-label={t("Readiness item {{row}}", {
                            row: index + 1,
                          })}
                          required
                          maxLength={200}
                          value={item.title}
                          onChange={(e) => {
                            update(item.key, { title: e.currentTarget.value });
                          }}
                        />
                      </td>
                      <td>
                        <TextInput
                          aria-label={t("Gate key {{row}}", { row: index + 1 })}
                          required
                          maxLength={64}
                          pattern="[A-Za-z0-9][A-Za-z0-9._-]*"
                          value={item.gateKey}
                          onChange={(e) => {
                            update(item.key, {
                              gateKey: e.currentTarget.value,
                            });
                          }}
                        />
                      </td>
                      <td>
                        <TextInput
                          aria-label={t("Weight {{row}}", { row: index + 1 })}
                          type="number"
                          required
                          min={1}
                          max={10000}
                          value={item.weight}
                          onChange={(e) => {
                            update(item.key, {
                              weight: Number(e.currentTarget.value),
                            });
                          }}
                        />
                      </td>
                      <td>
                        <Select
                          aria-label={t("Blocking level {{row}}", {
                            row: index + 1,
                          })}
                          value={item.blockingLevel}
                          onChange={(e) => {
                            update(item.key, {
                              blockingLevel: e.currentTarget
                                .value as ReadinessItemDefinition["blockingLevel"],
                            });
                          }}
                        >
                          <option value="P0">{t("P0")}</option>
                          <option value="P1">{t("P1")}</option>
                          <option value="P2">{t("P2")}</option>
                          <option value="none">{t("None")}</option>
                        </Select>
                      </td>
                      <td>
                        <input
                          aria-label={t("Required {{row}}", { row: index + 1 })}
                          type="checkbox"
                          checked={item.required}
                          onChange={(e) => {
                            update(item.key, {
                              required: e.currentTarget.checked,
                            });
                          }}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </fieldset>
          <div className="project-setup-toolbar">
            <Button
              visual="primary"
              type="submit"
              disabled={
                pending ||
                operation !== null ||
                !sessionCommandContext ||
                (retained !== null && !dirty)
              }
            >
              {t("Save readiness template draft")}
            </Button>
            {retained && !dirty ? (
              <Button
                type="button"
                disabled={
                  pending || !sessionCommandContext || operation !== null
                }
                onClick={() => {
                  setReview(true);
                }}
              >
                {t("Review template publication")}
              </Button>
            ) : null}
            <Button
              type="button"
              disabled={pending || (dirty && !requestWorkspaceTransition)}
              onClick={(event) => {
                if (requestWorkspaceTransition)
                  requestWorkspaceTransition(onClose, event.currentTarget);
                else onClose();
              }}
            >
              {t("Back to readiness")}
            </Button>
          </div>
          {retained ? (
            <SemanticStatus
              label={t("Readiness template draft saved")}
              tone="success"
            />
          ) : null}
          {pending ? (
            <p role="status" aria-busy="true">
              {t("Saving readiness template")}
            </p>
          ) : null}
          {failure && operation ? (
            <div role="alert">
              <RequestFailurePanel failure={failure} />
              <Button
                type="button"
                disabled={pending}
                onClick={() => {
                  void execute(operation);
                }}
              >
                {t("Retry exact template command")}
              </Button>
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
        {review && retained ? (
          <ImpactReview
            title={t("Review template publication")}
            confirmLabel={t("Publish readiness template")}
            reasonRequired={false}
            returnFocusTarget={() =>
              focus.current?.querySelector<HTMLElement>("ix-button, button") ??
              null
            }
            contextRows={[
              {
                label: t("Template"),
                value: retained.title,
                exempt: "business-data",
              },
              {
                label: t("Template version"),
                value: String(retained.templateVersion),
              },
              {
                label: t("Readiness items"),
                value: String(retained.items.length),
              },
            ]}
            details={{
              objectIdentity: retained.globalId,
              version: String(retained.optimisticVersion),
              impact: t(
                "Publishes the reviewed readiness template for new-tool Projects. Project initialization remains a separate action.",
              ),
              irreversible: t(
                "Published template versions cannot be overwritten.",
              ),
              permission: t("An enabled internal System Manager is required."),
              audit: t(
                "The command, receipt, actor and exact snapshot are audited atomically.",
              ),
              failureHandling: t(
                "Failures retain your inputs. Retry sends the same command identity and contents.",
              ),
            }}
            onCancel={() => {
              setReview(false);
            }}
            onConfirm={() => {
              void execute({
                kind: "publish",
                retained,
                key: `readiness-publish-${crypto.randomUUID()}`,
              });
            }}
          />
        ) : null}
      </Panel>
    </section>
  );
}
