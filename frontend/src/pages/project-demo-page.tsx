import { useState } from "react";

import type { GateStep, Scenario } from "../domain/view-models";
import { activities, gateSteps } from "../fixtures/prototype";
import {
  formatDate,
  formatDateTime,
  formatNumber,
  formatPercent,
} from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button } from "../ui-adapters/npi-ui";
import {
  DockedInspector,
  GateTrack,
  MetricStrip,
  ObjectHeader,
  SectionAnchors,
} from "../components/object-components";
import {
  DefinitionList,
  Panel,
  SemanticStatus,
} from "../components/primitives";

const source = {
  sourceSystem: "NPI_ONE" as const,
  editableIn: "NPI_ONE" as const,
  syncState: "partial" as const,
  lastSyncedAt: "2026-07-21T14:32:00Z",
};

export default function ProjectDemoPage({
  scenario,
  navigate,
}: {
  scenario: Scenario;
  navigate: (target: string) => void;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const [actionPrepared, setActionPrepared] = useState(false);
  const openGate = (step: GateStep): void => {
    const qualityQuery = step.code === "G6" ? "?quality=failed" : "";
    navigate(`/demo/projects/PJ-26018/gates/${step.code}${qualityQuery}`);
  };
  return (
    <article className="page page--object">
      <ObjectHeader
        code="PJ-26018"
        metadata={
          <span>
            {t("Customer")}:{" "}
            <span data-language-exempt="business-data">ACME</span> ·{" "}
            {t("Project manager")}:{" "}
            <span data-language-exempt="business-data">Alex Chen</span> ·{" "}
            {t("Target SOP")}:{" "}
            <time dateTime="2026-10-15">
              {formatDate(locale, "2026-10-15")}
            </time>
          </span>
        }
        name="Valve cover new tool"
        primaryAction={{
          disabled: scenario === "read_only",
          label: t("Prepare G5 review"),
          onClick: () => {
            navigate("/demo/projects/PJ-26018/gates/G5");
          },
        }}
        source={source}
        status={<SemanticStatus label={t("G4 trial iteration")} tone="info" />}
      />
      <GateTrack onSelect={openGate} steps={gateSteps} />
      <MetricStrip
        metrics={[
          { label: t("Overall progress"), value: formatPercent(locale, 0.68) },
          {
            label: t("Schedule variance"),
            value: t("{{days}} days", { days: formatNumber(locale, 4, 0) }),
            tone: "warning",
          },
          {
            label: t("Major blockers"),
            value: formatNumber(locale, 1, 0),
            tone: "danger",
          },
          { label: t("NPI readiness"), value: formatPercent(locale, 0.62) },
          {
            label: t("ERPNext execution"),
            value: t("{{count}} pending", {
              count: formatNumber(locale, 2, 0),
            }),
            tone: "warning",
          },
        ]}
      />
      <SectionAnchors
        sections={[
          { id: "project-structure", label: t("Project structure") },
          { id: "project-actions", label: t("Next actions and blockers") },
          { id: "project-properties", label: t("Object properties and risk") },
        ]}
      />
      {actionPrepared ? (
        <div className="scenario-banner scenario-banner--queued" role="status">
          {t("Prototype corrective action prepared. No action was saved.")}
        </div>
      ) : null}
      <div className="engineering-layout engineering-layout--project">
        <Panel id="project-structure" title={t("Project structure")}>
          <ul className="object-tree">
            <li>
              <SemanticStatus label={t("Product and design")} tone="success" />
              <small>{t("Baseline B02 released")}</small>
            </li>
            <li>
              <SemanticStatus label={t("Tooling")} tone="info" />
              <small data-language-exempt="identifier">TL-26018-01 · T1</small>
            </li>
            <li>
              <SemanticStatus label={t("Trial")} tone="warning" />
              <small>{t("T0 completed, T1 under analysis")}</small>
            </li>
            <li>
              <SemanticStatus label={t("Quality and samples")} tone="danger" />
              <small>
                {t("{{failed}} failed, {{pending}} pending", {
                  failed: formatNumber(locale, 1, 0),
                  pending: formatNumber(locale, 2, 0),
                })}
              </small>
            </li>
            <li>
              <SemanticStatus label={t("NPI")} tone="warning" />
              <small>
                {t("{{percent}} ready, {{count}} blockers", {
                  percent: formatPercent(locale, 0.62),
                  count: formatNumber(locale, 3, 0),
                })}
              </small>
            </li>
            <li>
              <SemanticStatus label={t("ERPNext")} tone="danger" />
              <small>
                {t("{{pending}} pending, {{failed}} exception", {
                  pending: formatNumber(locale, 2, 0),
                  failed: formatNumber(locale, 1, 0),
                })}
              </small>
            </li>
          </ul>
        </Panel>
        <Panel id="project-actions" title={t("Next actions and blockers")}>
          <div className="blocking-message">
            <SemanticStatus label={t("Major blocker")} tone="danger" />
            <strong>
              {t(
                "T1 cavity 3 flash is not verified and blocks G5 sample approval.",
              )}
            </strong>
            <div className="detail-actions">
              <Button
                disabled={scenario === "read_only"}
                onClick={() => {
                  setActionPrepared(true);
                }}
              >
                {t("Create corrective action")}
              </Button>
              <Button
                onClick={() => {
                  navigate("/demo/projects/PJ-26018/gates/G5");
                }}
              >
                {t("Open Gate review")}
              </Button>
            </div>
          </div>
          <table className="data-table data-table--compact">
            <thead>
              <tr>
                <th>{t("Due")}</th>
                <th>{t("Action")}</th>
                <th>{t("Responsible function")}</th>
                <th>{t("Status")}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{t("Today")}</td>
                <td>{t("Link the T1 dimensional report")}</td>
                <td>{t("Quality")}</td>
                <td>
                  <SemanticStatus label={t("Processing")} tone="info" />
                </td>
              </tr>
              <tr>
                <td>{t("Tomorrow")}</td>
                <td>{t("Confirm tooling correction revision B")}</td>
                <td>{t("Tooling engineering")}</td>
                <td>
                  <SemanticStatus label={t("Waiting")} tone="warning" />
                </td>
              </tr>
              <tr>
                <td>{t("Friday")}</td>
                <td>{t("Prepare the G5 review package")}</td>
                <td>{t("Project management")}</td>
                <td>
                  <SemanticStatus label={t("Not started")} />
                </td>
              </tr>
            </tbody>
          </table>
        </Panel>
        <DockedInspector
          activities={activities}
          id="project-properties"
          title={t("Object properties and risk")}
        >
          <DefinitionList
            rows={[
              { label: t("Current phase"), value: t("G4 trial iteration") },
              {
                label: t("Current design"),
                value: "Baseline B02",
                exempt: "identifier",
              },
              {
                label: t("Current tooling design"),
                value: "Revision C",
                exempt: "identifier",
              },
              { label: t("Project health"), value: t("Attention required") },
              { label: t("Budget used"), value: formatPercent(locale, 0.8) },
              {
                label: t("Last updated"),
                value: formatDateTime(locale, "2026-07-21T14:32:00Z"),
              },
            ]}
          />
        </DockedInspector>
      </div>
    </article>
  );
}
