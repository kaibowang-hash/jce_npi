import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type {
  ArchiveSourceKind,
  DataExchangeDataSource,
  DataExchangeDataset,
  DataExchangeProfile,
  DataExchangeWorkspace as Workspace,
  RetentionCategory,
  RetentionScope,
} from "../api/data-exchange-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { ObjectHeader } from "../components/object-components";
import { Panel, SemanticStatus } from "../components/primitives";
import { RequestFailurePanel } from "../components/problem-details-panel";
import { formatDate, formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, TextInput } from "../ui-adapters/npi-ui";

type ResourceState =
  | { kind: "loading" }
  | { kind: "loaded"; value: Workspace }
  | { kind: "failed"; failure: RequestFailure };
type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "failed"; failure: RequestFailure };

const reportColumns: Record<DataExchangeDataset, readonly string[]> = {
  "project_portfolio.v1": [
    "projectCode",
    "title",
    "projectType",
    "lifecycleState",
    "targetSop",
    "currentHealthStatus",
    "openWorkCount",
    "currentGate",
    "erpAvailability",
  ],
  "kpi_trends.v1": [
    "metricKey",
    "label",
    "valueKind",
    "sourceSystem",
    "availability",
    "reasonCode",
    "month",
    "value",
  ],
};
const categories: readonly RetentionCategory[] = [
  "project",
  "quality",
  "change",
  "file",
  "data_exchange_export",
  "controlled_print",
];
const sourceKinds: readonly ArchiveSourceKind[] = [
  "project",
  "quality_revision",
  "change_revision",
  "file_revision",
  "data_exchange_export",
  "controlled_print",
];
const source = {
  editableIn: "NPI_ONE" as const,
  sourceSystem: "NPI_ONE" as const,
  syncState: "local" as const,
};

export default function DataExchangeWorkspace({
  dataSource,
}: {
  dataSource: DataExchangeDataSource;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [resource, setResource] = useState<ResourceState>({ kind: "loading" });
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const [dataset, setDataset] = useState<DataExchangeDataset>(
    "project_portfolio.v1",
  );
  const [profileLanguage, setProfileLanguage] = useState<"en" | "zh" | "zh-TW">(
    locale,
  );
  const [maxRows, setMaxRows] = useState("500");
  const [fromMonth, setFromMonth] = useState("2026-01");
  const [toMonth, setToMonth] = useState("2026-12");
  const [scope, setScope] = useState<RetentionScope>("tenant");
  const [scopeReference, setScopeReference] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState("2026-01-01");
  const [retentionYears, setRetentionYears] = useState("7");
  const [sourceKind, setSourceKind] = useState<ArchiveSourceKind>("project");
  const [sourceId, setSourceId] = useState("");
  const [sourceVersion, setSourceVersion] = useState("1");
  const [sourceHash, setSourceHash] = useState("");
  const loadAbort = useRef<AbortController | null>(null);
  const commandAbort = useRef<AbortController | null>(null);

  const load = useCallback(() => {
    loadAbort.current?.abort();
    const controller = new AbortController();
    loadAbort.current = controller;
    void dataSource.load(controller.signal).then(
      (value) => {
        if (!controller.signal.aborted) setResource({ kind: "loaded", value });
      },
      (error: unknown) => {
        if (!controller.signal.aborted)
          setResource({ kind: "failed", failure: toRequestFailure(error) });
      },
    );
  }, [dataSource]);

  useEffect(() => {
    load();
    return () => {
      loadAbort.current?.abort();
      commandAbort.current?.abort();
    };
  }, [load]);

  const workspace = resource.kind === "loaded" ? resource.value : null;
  const latestPolicy = workspace?.retentionPolicies[0] ?? null;
  const latestProfile = useMemo(
    () =>
      workspace?.profiles.find((item) => item.datasetId === dataset) ?? null,
    [dataset, workspace],
  );

  const run = useCallback(
    async (
      label: string,
      operation: (signal: AbortSignal, key: string) => Promise<void>,
    ) => {
      if (!sessionCommandContext) return;
      commandAbort.current?.abort();
      const controller = new AbortController();
      commandAbort.current = controller;
      setCommand({ kind: "processing", label });
      try {
        await operation(
          controller.signal,
          `p9-06-${globalThis.crypto.randomUUID()}`,
        );
        if (!controller.signal.aborted) {
          setCommand({ kind: "idle" });
          load();
        }
      } catch (error) {
        if (!controller.signal.aborted)
          setCommand({ kind: "failed", failure: toRequestFailure(error) });
      }
    },
    [load, sessionCommandContext],
  );

  const context = useCallback(
    (signal: AbortSignal, idempotencyKey: string) => {
      if (!sessionCommandContext)
        throw new Error("Session command context is unavailable.");
      return {
        csrfToken: sessionCommandContext.csrfToken,
        idempotencyKey,
        signal,
      };
    },
    [sessionCommandContext],
  );

  const publishProfile = (): void => {
    void run(t("Publishing export profile"), async (signal, key) => {
      await dataSource.publishProfile(
        {
          globalId: crypto.randomUUID(),
          version: 1,
          datasetId: dataset,
          columns: reportColumns[dataset],
          language: profileLanguage,
          redactionProfile: "minimum_disclosure.v1",
          query: dataset === "kpi_trends.v1" ? { fromMonth, toMonth } : {},
          maxRows: Number(maxRows),
          maxBytes: 8_000_000,
        },
        context(signal, key),
      );
    });
  };

  const createExport = (profile: DataExchangeProfile): void => {
    void run(t("Creating report package"), async (signal, key) => {
      await dataSource.createExport(profile, context(signal, key));
    });
  };

  const downloadExport = (value: Workspace["exports"][number]): void => {
    void run(t("Downloading report package"), async (signal, key) => {
      const blob = await dataSource.downloadExport(value, context(signal, key));
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = value.artifact.fileName;
      anchor.click();
      URL.revokeObjectURL(url);
    });
  };

  const publishPolicy = (): void => {
    void run(t("Publishing retention policy"), async (signal, key) => {
      const years = Number(retentionYears);
      await dataSource.publishPolicy(
        {
          globalId: crypto.randomUUID(),
          version: 1,
          scope,
          scopeReference: scope === "tenant" ? null : scopeReference.trim(),
          effectiveFrom,
          effectiveUntil: null,
          retentionYears: Object.fromEntries(
            categories.map((category) => [category, years]),
          ) as Record<RetentionCategory, number>,
        },
        context(signal, key),
      );
    });
  };

  const createArchive = (): void => {
    if (!latestPolicy) return;
    void run(t("Creating archive record"), async (signal, key) => {
      await dataSource.createArchive(
        {
          globalId: crypto.randomUUID(),
          sourceKind,
          sourceId: sourceId.trim(),
          sourceVersion: Number(sourceVersion),
          sourceHash: sourceHash.trim(),
          policyId: latestPolicy.globalId,
          policyVersion: latestPolicy.version,
          policyHash: latestPolicy.definitionHash,
          scope: latestPolicy.scope,
          scopeReference: latestPolicy.scopeReference,
        },
        context(signal, key),
      );
    });
  };

  return (
    <article
      className="page page--reporting data-exchange"
      data-testid="data-exchange-workspace"
    >
      <ObjectHeader
        code={t("Administration")}
        name={t("Data Exchange")}
        nameIsBusinessData={false}
        metadata={t(
          "Publish bounded report profiles and retention policies, then inspect immutable export and archive truth.",
        )}
        source={source}
        secondaryAction={
          <Button
            icon="refresh"
            onClick={() => {
              setResource({ kind: "loading" });
              load();
            }}
          >
            {t("Refresh")}
          </Button>
        }
        status={
          <SemanticStatus
            label={
              workspace?.routesEnabled
                ? t("Routes enabled")
                : t("Routes disabled")
            }
            tone={workspace?.routesEnabled ? "warning" : "neutral"}
          />
        }
      />
      {resource.kind === "loading" ? (
        <section aria-busy="true" className="state-surface">
          {t("Loading Data Exchange workspace")}
        </section>
      ) : null}
      {resource.kind === "failed" ? (
        <section className="state-surface" role="alert">
          <h2>{t("Data Exchange workspace unavailable")}</h2>
          <RequestFailurePanel failure={resource.failure} />
          <Button icon="refresh" onClick={load}>
            {t("Retry")}
          </Button>
        </section>
      ) : null}
      {command.kind === "processing" ? (
        <section aria-busy="true" className="state-surface">
          {command.label}
        </section>
      ) : null}
      {command.kind === "failed" ? (
        <section className="state-surface" role="alert">
          <RequestFailurePanel failure={command.failure} />
        </section>
      ) : null}
      {workspace ? (
        <div className="data-exchange__grid">
          <Panel title={t("Capability catalog")}>
            <p>
              {t(
                "Existing specialized exchanges remain independent. Only the two reporting datasets can be exported here.",
              )}
            </p>
            <table className="engineering-table">
              <thead>
                <tr>
                  <th>{t("Capability")}</th>
                  <th>{t("Mode")}</th>
                  <th>{t("Exportable here")}</th>
                </tr>
              </thead>
              <tbody>
                {workspace.capabilities.map((item) => (
                  <tr key={item.id}>
                    <td data-language-exempt="identifier">{item.id}</td>
                    <td>
                      {item.mode === "report_export_profile"
                        ? t("Report export profile")
                        : t("Independent specialized operation")}
                    </td>
                    <td>{item.exportableHere ? t("Yes") : t("No")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Panel>

          <Panel title={t("Published export profiles")}>
            <div className="data-exchange__form">
              <label>
                {t("Dataset")}
                <select
                  aria-label={t("Dataset")}
                  value={dataset}
                  onChange={(event) => {
                    setDataset(event.target.value as DataExchangeDataset);
                  }}
                >
                  <option value="project_portfolio.v1">
                    {t("Project portfolio dataset")}
                  </option>
                  <option value="kpi_trends.v1">
                    {t("KPI trends dataset")}
                  </option>
                </select>
              </label>
              <label>
                {t("Language")}
                <select
                  aria-label={t("Language")}
                  value={profileLanguage}
                  onChange={(event) => {
                    setProfileLanguage(
                      event.target.value as "en" | "zh" | "zh-TW",
                    );
                  }}
                >
                  <option value="en">{t("English")}</option>
                  <option value="zh">{t("Simplified Chinese")}</option>
                  <option value="zh-TW">{t("Traditional Chinese")}</option>
                </select>
              </label>
              <label>
                {t("Maximum rows")}
                <TextInput
                  value={maxRows}
                  onChange={(event) => {
                    setMaxRows(event.target.value);
                  }}
                />
              </label>
              {dataset === "kpi_trends.v1" ? (
                <>
                  <label>
                    {t("From month")}
                    <TextInput
                      value={fromMonth}
                      onChange={(event) => {
                        setFromMonth(event.target.value);
                      }}
                    />
                  </label>
                  <label>
                    {t("To month")}
                    <TextInput
                      value={toMonth}
                      onChange={(event) => {
                        setToMonth(event.target.value);
                      }}
                    />
                  </label>
                </>
              ) : null}
              <Button
                disabled={
                  !sessionCommandContext || command.kind === "processing"
                }
                onClick={publishProfile}
              >
                {t("Publish profile")}
              </Button>
            </div>
            {workspace.profiles.length === 0 ? (
              <p>{t("No export profiles are published.")}</p>
            ) : (
              <table className="engineering-table">
                <thead>
                  <tr>
                    <th>{t("Dataset")}</th>
                    <th>{t("Version")}</th>
                    <th>{t("Language")}</th>
                    <th>{t("Published at")}</th>
                    <th>{t("Action")}</th>
                  </tr>
                </thead>
                <tbody>
                  {workspace.profiles.map((item) => (
                    <tr key={item.globalId}>
                      <td data-language-exempt="identifier">
                        {item.datasetId}
                      </td>
                      <td>{formatNumber(locale, item.version)}</td>
                      <td data-language-exempt="identifier">{item.language}</td>
                      <td>{formatDateTime(locale, item.publishedAt)}</td>
                      <td>
                        <Button
                          disabled={
                            !sessionCommandContext ||
                            command.kind === "processing"
                          }
                          onClick={() => {
                            createExport(item);
                          }}
                        >
                          {t("Create package")}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {latestProfile ? (
              <p>
                {t("The newest selected profile is hash-bound and immutable.")}{" "}
                <code data-language-exempt="identifier">
                  {latestProfile.definitionHash.slice(0, 12)}
                </code>
              </p>
            ) : null}
          </Panel>

          <Panel title={t("Immutable exports")}>
            {workspace.exports.length === 0 ? (
              <p>{t("No report packages have been created.")}</p>
            ) : (
              <table className="engineering-table">
                <thead>
                  <tr>
                    <th>{t("File")}</th>
                    <th>{t("Rows")}</th>
                    <th>{t("Created at")}</th>
                    <th>{t("Action")}</th>
                  </tr>
                </thead>
                <tbody>
                  {workspace.exports.map((item) => (
                    <tr key={item.globalId}>
                      <td data-language-exempt="identifier">
                        {item.artifact.fileName}
                      </td>
                      <td>{formatNumber(locale, item.rowCount)}</td>
                      <td>{formatDateTime(locale, item.createdAt)}</td>
                      <td>
                        <Button
                          icon="document"
                          disabled={
                            !sessionCommandContext ||
                            command.kind === "processing"
                          }
                          onClick={() => {
                            downloadExport(item);
                          }}
                        >
                          {t("Download")}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>

          <Panel title={t("Published retention policies")}>
            <p>
              {t(
                "No default policy or precedence is inferred. Every archive binds one exact policy version.",
              )}
            </p>
            <div className="data-exchange__form">
              <label>
                {t("Scope")}
                <select
                  aria-label={t("Scope")}
                  value={scope}
                  onChange={(event) => {
                    setScope(event.target.value as RetentionScope);
                  }}
                >
                  <option value="tenant">{t("Tenant")}</option>
                  <option value="customer_reference">
                    {t("Customer reference")}
                  </option>
                  <option value="regulation_reference">
                    {t("Regulation reference")}
                  </option>
                </select>
              </label>
              {scope !== "tenant" ? (
                <label>
                  {t("Scope reference")}
                  <TextInput
                    value={scopeReference}
                    onChange={(event) => {
                      setScopeReference(event.target.value);
                    }}
                  />
                </label>
              ) : null}
              <label>
                {t("Effective from")}
                <TextInput
                  value={effectiveFrom}
                  onChange={(event) => {
                    setEffectiveFrom(event.target.value);
                  }}
                />
              </label>
              <label>
                {t("Retention years")}
                <TextInput
                  value={retentionYears}
                  onChange={(event) => {
                    setRetentionYears(event.target.value);
                  }}
                />
              </label>
              <Button
                disabled={
                  !sessionCommandContext || command.kind === "processing"
                }
                onClick={publishPolicy}
              >
                {t("Publish policy")}
              </Button>
            </div>
            {workspace.retentionPolicies.length === 0 ? (
              <p>{t("No retention policies are published.")}</p>
            ) : (
              <ul className="data-exchange__records">
                {workspace.retentionPolicies.map((item) => (
                  <li key={item.globalId}>
                    <strong>
                      {item.scope === "tenant"
                        ? t("Tenant")
                        : item.scope === "customer_reference"
                          ? t("Customer reference")
                          : t("Regulation reference")}
                    </strong>
                    <span>
                      {formatDate(locale, item.effectiveFrom)} · {t("Version")}{" "}
                      {formatNumber(locale, item.version)}
                    </span>
                    <code data-language-exempt="identifier">
                      {item.definitionHash.slice(0, 12)}
                    </code>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title={t("Append-only archive records")}>
            <p>
              {t(
                "Creating an archive record never changes, deletes or disposes the source.",
              )}
            </p>
            <div className="data-exchange__form">
              <label>
                {t("Source kind")}
                <select
                  aria-label={t("Source kind")}
                  value={sourceKind}
                  onChange={(event) => {
                    setSourceKind(event.target.value as ArchiveSourceKind);
                  }}
                >
                  {sourceKinds.map((kind) => (
                    <option
                      data-language-exempt="identifier"
                      key={kind}
                      value={kind}
                    >
                      {kind}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t("Source ID")}
                <TextInput
                  value={sourceId}
                  onChange={(event) => {
                    setSourceId(event.target.value);
                  }}
                />
              </label>
              <label>
                {t("Source version")}
                <TextInput
                  value={sourceVersion}
                  onChange={(event) => {
                    setSourceVersion(event.target.value);
                  }}
                />
              </label>
              <label>
                {t("Source hash")}
                <TextInput
                  value={sourceHash}
                  onChange={(event) => {
                    setSourceHash(event.target.value);
                  }}
                />
              </label>
              <Button
                disabled={
                  !sessionCommandContext ||
                  !latestPolicy ||
                  command.kind === "processing"
                }
                onClick={createArchive}
              >
                {t("Create archive record")}
              </Button>
            </div>
            {workspace.archiveRecords.length === 0 ? (
              <p>{t("No archive records have been created.")}</p>
            ) : (
              <ul className="data-exchange__records">
                {workspace.archiveRecords.map((item) => (
                  <li key={item.globalId}>
                    <strong data-language-exempt="identifier">
                      {item.sourceKind}
                    </strong>
                    <span>
                      {t("Retain until")} {formatDate(locale, item.retainUntil)}
                    </span>
                    <code data-language-exempt="identifier">
                      {item.sourceHash.slice(0, 12)}
                    </code>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      ) : null}
    </article>
  );
}
