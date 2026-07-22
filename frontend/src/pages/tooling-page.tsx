import { useState } from "react";

import type { Scenario } from "../domain/view-models";
import { activities, lifecycleSteps } from "../fixtures/prototype";
import {
  formatCurrency,
  formatDate,
  formatNumber,
  formatPercent,
} from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button } from "../ui-adapters/npi-ui";
import {
  DockedInspector,
  LifecycleTrack,
  ObjectHeader,
  SectionAnchors,
} from "../components/object-components";
import {
  DefinitionList,
  ImpactReview,
  Panel,
  SemanticStatus,
  SourceBadge,
  SyncBadge,
} from "../components/primitives";

const toolingSource = {
  sourceSystem: "NPI_ONE" as const,
  editableIn: "NPI_ONE" as const,
  syncState: "pending" as const,
};
const erpSource = {
  sourceSystem: "ERPNEXT" as const,
  editableIn: "ERPNEXT" as const,
  syncState: "stale" as const,
  externalReference: "ASSET-PENDING",
};

export default function ToolingPage({
  scenario,
  navigate,
}: {
  scenario: Scenario;
  navigate: (target: string) => void;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const [reviewKind, setReviewKind] = useState<"design" | "acceptance" | null>(
    null,
  );
  const [designPreparedReason, setDesignPreparedReason] = useState<
    string | null
  >(null);
  const [acceptancePreparedReason, setAcceptancePreparedReason] = useState<
    string | null
  >(null);
  return (
    <article className="page page--object">
      <ObjectHeader
        code="TL-26018-01"
        metadata={
          <span>
            {t("Ownership")}: {t("Company owned")} · {t("Cavities")}:{" "}
            {formatNumber(locale, 4, 0)} · {t("Supplier")}:{" "}
            <span data-language-exempt="business-data">K-Tech</span> ·{" "}
            {t("Target acceptance")}:{" "}
            <time dateTime="2026-08-30">
              {formatDate(locale, "2026-08-30")}
            </time>
          </span>
        }
        name="Valve cover injection tool"
        primaryAction={{
          disabled: scenario === "read_only",
          label: t("Create T1 from T0"),
          onClick: () => {
            navigate("/trials/T1?inherit=T0");
          },
        }}
        source={toolingSource}
        status={
          <SemanticStatus label={t("T1 analysis in progress")} tone="info" />
        }
      />
      <LifecycleTrack steps={lifecycleSteps} />
      <SectionAnchors
        sections={[
          { id: "tooling-structure", label: t("Tooling object tree") },
          {
            id: "tooling-milestones",
            label: t("Milestones and trial records"),
          },
          {
            id: "tooling-properties",
            label: t("Properties and ERPNext mapping"),
          },
        ]}
      />
      {designPreparedReason ? (
        <div className="scenario-banner scenario-banner--queued" role="status">
          <span>
            {t(
              "Prototype release command prepared. Revision C remains unchanged.",
            )}
          </span>
          <span>
            {t(
              "The in-memory prototype command captured a reason; no audit record was persisted.",
            )}
          </span>
        </div>
      ) : null}
      {acceptancePreparedReason ? (
        <div className="scenario-banner scenario-banner--queued" role="status">
          <span>
            {t(
              "Prototype acceptance request prepared. ERPNext asset execution has not started.",
            )}
          </span>
          <span>
            {t(
              "The in-memory prototype command captured a reason; no audit record was persisted.",
            )}
          </span>
          <Button
            onClick={() => {
              navigate("/execution?focus=EX-260721-0048");
            }}
          >
            {t("View execution")}
          </Button>
        </div>
      ) : null}
      <div className="engineering-layout">
        <Panel id="tooling-structure" title={t("Tooling object tree")}>
          <ul className="object-tree">
            <li>
              <SemanticStatus label={t("Tooling requirement")} tone="success" />
              <small>{t("Approved")}</small>
            </li>
            <li>
              <SemanticStatus label={t("Design revisions")} tone="success" />
              <small data-language-exempt="identifier">A · B · C</small>
            </li>
            <li>
              <SemanticStatus
                label={t("Manufacturing milestones")}
                tone="success"
              />
              <small>
                {t("{{complete}} of {{total}} complete", {
                  complete: formatNumber(locale, 8, 0),
                  total: formatNumber(locale, 8, 0),
                })}
              </small>
            </li>
            <li>
              <SemanticStatus label={t("Trial rounds")} tone="info" />
              <small>{t("T0 completed, T1 under analysis")}</small>
            </li>
            <li>
              <SemanticStatus label={t("Defects")} tone="danger" />
              <small>
                {t("{{major}} major, {{minor}} minor", {
                  major: formatNumber(locale, 2, 0),
                  minor: formatNumber(locale, 4, 0),
                })}
              </small>
            </li>
            <li>
              <SemanticStatus label={t("Acceptance checklist")} />
              <small>{t("Not started")}</small>
            </li>
            <li>
              <SemanticStatus label={t("ERPNext asset")} tone="warning" />
              <small>{t("Execution request not created")}</small>
            </li>
          </ul>
        </Panel>
        <Panel
          actions={
            <Button
              disabled={scenario === "read_only"}
              onClick={() => {
                setReviewKind("design");
              }}
            >
              {t("Release design revision")}
            </Button>
          }
          id="tooling-milestones"
          title={t("Milestones and trial records")}
        >
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("Node or round")}</th>
                <th>{t("Date")}</th>
                <th>{t("Design version")}</th>
                <th>{t("Result")}</th>
                <th>{t("Status")}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{t("Design release")}</td>
                <td>
                  <time dateTime="2026-07-05">
                    {formatDate(locale, "2026-07-05")}
                  </time>
                </td>
                <td data-language-exempt="identifier">Revision C</td>
                <td>{t("Approved")}</td>
                <td>
                  <SemanticStatus label={t("Completed")} tone="success" />
                </td>
              </tr>
              <tr>
                <td>{t("Manufacturing complete")}</td>
                <td>
                  <time dateTime="2026-07-15">
                    {formatDate(locale, "2026-07-15")}
                  </time>
                </td>
                <td data-language-exempt="identifier">Revision C</td>
                <td>
                  {t("{{days}} days late", {
                    days: formatNumber(locale, 3, 0),
                  })}
                </td>
                <td>
                  <SemanticStatus label={t("Completed")} tone="success" />
                </td>
              </tr>
              <tr>
                <td data-language-exempt="identifier">T0</td>
                <td>
                  <time dateTime="2026-06-28">
                    {formatDate(locale, "2026-06-28")}
                  </time>
                </td>
                <td data-language-exempt="identifier">Revision B</td>
                <td>
                  {t("{{percent}} yield", {
                    percent: formatPercent(locale, 0.76),
                  })}
                </td>
                <td>
                  <SemanticStatus
                    label={t("Tooling change required")}
                    tone="warning"
                  />
                </td>
              </tr>
              <tr>
                <td data-language-exempt="identifier">T1</td>
                <td>
                  <time dateTime="2026-07-18">
                    {formatDate(locale, "2026-07-18")}
                  </time>
                </td>
                <td data-language-exempt="identifier">Revision C</td>
                <td>
                  {t("{{percent}} yield", {
                    percent: formatPercent(locale, 0.91),
                  })}
                </td>
                <td>
                  <SemanticStatus label={t("Under analysis")} tone="info" />
                </td>
              </tr>
            </tbody>
          </table>
          <div className="blocking-message">
            <SemanticStatus label={t("Current major defect")} tone="danger" />
            <strong>{t("DEF-014: Flash on cavity 3 parting line")}</strong>
            <Button
              onClick={() => {
                navigate("/projects/PJ-26018/gates/G5");
              }}
            >
              {t("Open defect context")}
            </Button>
          </div>
        </Panel>
        <DockedInspector
          activities={activities}
          id="tooling-properties"
          title={t("Properties and ERPNext mapping")}
        >
          <DefinitionList
            rows={[
              {
                label: t("Current design"),
                value: (
                  <>
                    <span data-language-exempt="identifier">Revision C</span> ·{" "}
                    {t("Released and immutable")}
                  </>
                ),
              },
              {
                label: t("Tooling supplier"),
                value: "K-Tech",
                exempt: "business-data",
              },
              {
                label: t("Purchase execution"),
                value: (
                  <>
                    <span data-language-exempt="identifier">PO-260144</span> ·{" "}
                    {t("Completed")}
                  </>
                ),
              },
              {
                label: t("Committed cost"),
                value: formatCurrency(locale, 428000, "CNY"),
                exempt: "unit",
              },
              {
                label: t("Actual cost"),
                value: formatCurrency(locale, 440000, "CNY"),
                exempt: "unit",
              },
              {
                label: t("Asset handover"),
                value: t("Waiting for tooling acceptance"),
              },
              {
                label: t("Why read only"),
                value: t(
                  "ERPNext owns the formal asset identifier, location, and maintenance state.",
                ),
              },
            ]}
          />
          <div className="inspector-badges">
            <SourceBadge source={erpSource} />
            <SyncBadge state={erpSource.syncState} />
          </div>
          <Button
            disabled={scenario === "read_only"}
            onClick={() => {
              setReviewKind("acceptance");
            }}
          >
            {t("Review tooling acceptance")}
          </Button>
          <Button
            onClick={() => {
              navigate("/execution");
            }}
          >
            {t("View ERPNext execution conditions")}
          </Button>
        </DockedInspector>
      </div>
      {reviewKind === "design" ? (
        <ImpactReview
          confirmLabel={t("Prepare release command")}
          details={{
            objectIdentity: "TL-26018-01",
            version: "Revision C",
            impact: t(
              "Manufacturing and future Trial references will use this released revision.",
            ),
            permission: t("Tooling design approver permission is required."),
            irreversible: t(
              "The released revision cannot be overwritten; a new revision is required.",
            ),
            failureHandling: t(
              "A failed command leaves the current released revision unchanged.",
            ),
            audit: t(
              "A submitted command would record the source files, hashes, approver, reason, and trace ID.",
            ),
          }}
          onCancel={() => {
            setReviewKind(null);
          }}
          onConfirm={(reason) => {
            setReviewKind(null);
            setDesignPreparedReason(reason);
          }}
          title={t("Tooling design release impact review")}
        />
      ) : null}
      {reviewKind === "acceptance" ? (
        <ImpactReview
          confirmLabel={t("Prepare acceptance command")}
          details={{
            objectIdentity: "TL-26018-01",
            version: "Acceptance snapshot v1",
            impact: t(
              "Acceptance will freeze the technical, quality, file, warranty, cost, and asset handover evidence.",
            ),
            permission: t(
              "Tooling acceptance approver permission is required.",
            ),
            irreversible: t(
              "The historical acceptance snapshot cannot be overwritten.",
            ),
            failureHandling: t(
              "A failed command leaves Tooling in development and creates no ERPNext execution request.",
            ),
            audit: t(
              "A submitted command would record the checklist versions, approver, reason, result, and trace ID.",
            ),
          }}
          onCancel={() => {
            setReviewKind(null);
          }}
          onConfirm={(reason) => {
            setReviewKind(null);
            setAcceptancePreparedReason(reason);
          }}
          title={t("Tooling acceptance impact review")}
        />
      ) : null}
    </article>
  );
}
