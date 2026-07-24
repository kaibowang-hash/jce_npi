import { useState } from "react";

import type { Scenario } from "../domain/view-models";
import { activities } from "../fixtures/prototype";
import { formatNumber, formatPercent } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button } from "../ui-adapters/npi-ui";
import { DockedInspector, ObjectHeader } from "../components/object-components";
import {
  DefinitionList,
  ImpactReview,
  Panel,
  SemanticStatus,
} from "../components/primitives";

const source = {
  sourceSystem: "NPI_ONE" as const,
  editableIn: "NPI_ONE" as const,
  syncState: "local" as const,
};
type TrialTab =
  | "parameters"
  | "samples"
  | "defects"
  | "measurements"
  | "comparison";

export default function TrialPage({
  scenario,
  navigate,
}: {
  scenario: Scenario;
  navigate: (target: string) => void;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const [reviewOpen, setReviewOpen] = useState(false);
  const [preparedReason, setPreparedReason] = useState<string | null>(null);
  const [photoSelection, setPhotoSelection] = useState<{
    fileName: string;
    valid: boolean;
  } | null>(null);
  const [activeTab, setActiveTab] = useState<TrialTab>("parameters");
  const inheritedFrom = new URLSearchParams(globalThis.location.search).get(
    "inherit",
  );
  const inherited = inheritedFrom === "T0";
  const trialCode = "T1";
  const tabs: readonly { id: TrialTab; label: string }[] = [
    { id: "parameters", label: t("Parameters") },
    { id: "samples", label: t("Samples and cavities") },
    { id: "defects", label: t("Defects") },
    { id: "measurements", label: t("Measurements") },
    { id: "comparison", label: t("Round comparison") },
  ];
  const selectAdjacentTab = (current: TrialTab, direction: -1 | 1): void => {
    const currentIndex = tabs.findIndex((tab) => tab.id === current);
    const nextIndex = (currentIndex + direction + tabs.length) % tabs.length;
    const next = tabs[nextIndex];
    if (!next) return;
    setActiveTab(next.id);
    globalThis.queueMicrotask(() =>
      document.querySelector<HTMLElement>(`#trial-tab-${next.id}`)?.focus(),
    );
  };
  return (
    <article className="page page--object">
      <ObjectHeader
        code={`${trialCode} / TL-26018-01`}
        metadata={
          <span>
            {t("Tooling")}:{" "}
            <span data-language-exempt="identifier">TL-26018-01</span> ·{" "}
            {t("Part")}: <span data-language-exempt="identifier">VC-01</span> ·{" "}
            {t("Machine")}:{" "}
            <span data-language-exempt="identifier">IM-550-02</span>
          </span>
        }
        name={inherited ? t("Inherited trial plan") : t("Trial round")}
        nameIsBusinessData={false}
        primaryAction={{
          disabled: scenario === "read_only",
          label: t("Submit trial conclusion"),
          onClick: () => {
            setReviewOpen(true);
          },
        }}
        source={source}
        status={
          <SemanticStatus
            label={inherited ? t("Planned from T0") : t("Analysis in progress")}
            tone="info"
          />
        }
      />
      <div className="locked-inputs">
        <SemanticStatus label={t("Input versions locked")} tone="success" />
        <span>
          {t("Product baseline")}:{" "}
          <strong data-language-exempt="identifier">B02</strong>
        </span>
        <span>
          {t("Tooling design")}:{" "}
          <strong data-language-exempt="identifier">Revision C</strong>
        </span>
        <span>
          {t("Material batch")}:{" "}
          <strong data-language-exempt="identifier">PA66-GF30 / M260715</strong>
        </span>
        <span>
          {t("Parameter template")}:{" "}
          <strong data-language-exempt="identifier">P-07</strong>
        </span>
      </div>
      {preparedReason ? (
        <div className="scenario-banner scenario-banner--queued" role="status">
          <span>
            {t(
              "Prototype conclusion command prepared. The Trial snapshot was not submitted.",
            )}
          </span>
          <span>
            {t(
              "The in-memory prototype command captured a reason; no audit record was persisted.",
            )}
          </span>
        </div>
      ) : null}
      <div className="trial-layout">
        <Panel title={t("Inputs and evidence")}>
          <ul className="object-tree">
            <li>
              <SemanticStatus label={t("Plan and resources")} tone="success" />
              <small>{t("Confirmed")}</small>
            </li>
            <li>
              <SemanticStatus label={t("Product and drawing")} tone="success" />
              <small data-language-exempt="identifier">Baseline B02</small>
            </li>
            <li>
              <SemanticStatus label={t("Tooling design")} tone="success" />
              <small data-language-exempt="identifier">Revision C</small>
            </li>
            <li>
              <SemanticStatus label={t("Material batch")} tone="success" />
              <small data-language-exempt="identifier">M260715</small>
            </li>
            <li>
              <SemanticStatus label={t("Process parameters")} tone="info" />
              <small data-language-exempt="identifier">P-07</small>
            </li>
            <li>
              <SemanticStatus label={t("Samples and cavities")} tone="info" />
              <small>
                {t("{{samples}} samples, {{cavities}} cavities", {
                  samples: formatNumber(locale, 80, 0),
                  cavities: formatNumber(locale, 4, 0),
                })}
              </small>
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
              <SemanticStatus label={t("Measurement report")} tone="warning" />
              <small>
                {t("{{count}} item awaiting linkage", {
                  count: formatNumber(locale, 1, 0),
                })}
              </small>
            </li>
          </ul>
          <label
            aria-disabled={scenario === "read_only"}
            className={`photo-action${scenario === "read_only" ? " photo-action--disabled" : ""}`}
          >
            <input
              accept="image/*"
              aria-label={t("Add trial photo")}
              capture="environment"
              className="visually-hidden"
              disabled={scenario === "read_only"}
              onChange={(event) => {
                const file = event.currentTarget.files?.[0];
                if (!file) {
                  setPhotoSelection(null);
                  return;
                }
                setPhotoSelection({
                  fileName: file.name,
                  valid: file.type.startsWith("image/"),
                });
              }}
              type="file"
            />
            <span className="photo-action__button">{t("Add trial photo")}</span>
          </label>
          {photoSelection ? (
            <div className="scenario-banner" role="status">
              <span>
                {photoSelection.valid
                  ? t("Prototype photo selected. No file was uploaded.")
                  : t(
                      "The selected file is not an image. No upload was prepared.",
                    )}
              </span>
              <span data-language-exempt="business-data">
                {photoSelection.fileName}
              </span>
            </div>
          ) : null}
        </Panel>
        <Panel title={t("Trial record")}>
          <div
            className="rectangular-tabs"
            role="tablist"
            aria-label={t("Trial record sections")}
          >
            {tabs.map((tab) => (
              <button
                aria-controls="trial-record-panel"
                aria-selected={activeTab === tab.id}
                id={`trial-tab-${tab.id}`}
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id);
                }}
                onKeyDown={(event) => {
                  if (event.key === "ArrowRight") selectAdjacentTab(tab.id, 1);
                  if (event.key === "ArrowLeft") selectAdjacentTab(tab.id, -1);
                }}
                role="tab"
                tabIndex={activeTab === tab.id ? 0 : -1}
                type="button"
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div
            aria-labelledby={`trial-tab-${activeTab}`}
            id="trial-record-panel"
            role="tabpanel"
          >
            {activeTab === "parameters" ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("Parameter")}</th>
                    <th>{t("Template value")}</th>
                    <th>{t("Actual value")}</th>
                    <th>{t("Unit")}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>{t("Melt temperature")}</td>
                    <td>{formatNumber(locale, 285, 0)}</td>
                    <td>{formatNumber(locale, 288, 0)}</td>
                    <td data-language-exempt="unit">°C</td>
                  </tr>
                  <tr>
                    <td>{t("Tool temperature")}</td>
                    <td>{formatNumber(locale, 85, 0)}</td>
                    <td>{formatNumber(locale, 86, 0)}</td>
                    <td data-language-exempt="unit">°C</td>
                  </tr>
                  <tr>
                    <td>{t("Injection pressure")}</td>
                    <td>{formatNumber(locale, 92, 0)}</td>
                    <td>{formatNumber(locale, 96, 0)}</td>
                    <td data-language-exempt="unit">MPa</td>
                  </tr>
                  <tr>
                    <td>{t("Holding time")}</td>
                    <td>{formatNumber(locale, 9)}</td>
                    <td>{formatNumber(locale, 9.5)}</td>
                    <td data-language-exempt="unit">s</td>
                  </tr>
                  <tr>
                    <td>{t("Cooling time")}</td>
                    <td>{formatNumber(locale, 24, 0)}</td>
                    <td>{formatNumber(locale, 23, 0)}</td>
                    <td data-language-exempt="unit">s</td>
                  </tr>
                  <tr>
                    <td>{t("Cycle time")}</td>
                    <td>{formatNumber(locale, 38)}</td>
                    <td>{formatNumber(locale, 36.5)}</td>
                    <td data-language-exempt="unit">s</td>
                  </tr>
                </tbody>
              </table>
            ) : activeTab === "samples" ? (
              <DefinitionList
                rows={[
                  {
                    label: t("Samples and cavities"),
                    value: t("{{samples}} samples, {{cavities}} cavities", {
                      samples: formatNumber(locale, 80, 0),
                      cavities: formatNumber(locale, 4, 0),
                    }),
                  },
                  { label: t("Customer samples"), value: t("Not submitted") },
                ]}
              />
            ) : activeTab === "defects" ? (
              <div className="blocking-message">
                <SemanticStatus label={t("Major defects")} tone="danger" />
                <p>
                  {t(
                    "The dimensional report is not linked and two major defects remain open.",
                  )}
                </p>
              </div>
            ) : activeTab === "measurements" ? (
              <DefinitionList
                rows={[
                  {
                    label: t("Measurement report"),
                    value: t("{{count}} item awaiting linkage", {
                      count: formatNumber(locale, 1, 0),
                    }),
                  },
                  {
                    label: t("Dimensional status"),
                    value: t("{{failed}} failed, {{passed}} passed", {
                      failed: formatNumber(locale, 1, 0),
                      passed: formatNumber(locale, 8, 0),
                    }),
                  },
                ]}
              />
            ) : (
              <p className="comparison-summary">
                {t(
                  "Compared with T0: tooling design B → C; holding +0.5 s; cooling −1 s.",
                )}
              </p>
            )}
          </div>
        </Panel>
        <DockedInspector
          activities={activities}
          title={t("Conclusion and next step")}
        >
          <DefinitionList
            rows={[
              {
                label: t("Overall conclusion"),
                value: t("Repeat trial required"),
              },
              { label: t("Yield"), value: formatPercent(locale, 0.91) },
              {
                label: t("Major defects"),
                value: formatNumber(locale, 2, 0),
              },
              {
                label: t("Dimensional status"),
                value: t("{{failed}} failed, {{passed}} passed", {
                  failed: formatNumber(locale, 1, 0),
                  passed: formatNumber(locale, 8, 0),
                }),
              },
              { label: t("Customer samples"), value: t("Not submitted") },
              {
                label: t("Suggested next round"),
                value: inherited ? "T3" : "T2",
                exempt: "identifier",
              },
            ]}
          />
          <div className="blocking-message">
            <SemanticStatus label={t("Pre-submit checks")} tone="danger" />
            <p>
              {t(
                "The dimensional report is not linked and two major defects remain open.",
              )}
            </p>
            <Button
              onClick={() => {
                navigate("/demo/projects/PJ-26018/gates/G5");
              }}
            >
              {t("View blockers")}
            </Button>
          </div>
        </DockedInspector>
      </div>
      {reviewOpen ? (
        <ImpactReview
          confirmLabel={t("Prepare conclusion command")}
          details={{
            objectIdentity: `${trialCode} / TL-26018-01`,
            version: "Input snapshot 7e31…a218",
            impact: t(
              "The submitted Trial will freeze tooling, product, material, plan, parameter, sample, and defect inputs.",
            ),
            permission: t("Trial submitter permission is required."),
            irreversible: t(
              "A submitted round cannot be overwritten; correction requires a controlled reopen or a new round.",
            ),
            failureHandling: t(
              "A failed command leaves the Trial in analysis and returns field errors with a trace ID.",
            ),
            audit: t(
              "A submitted command would record the actor, conclusion, reason, input hash, result, and trace ID.",
            ),
          }}
          onCancel={() => {
            setReviewOpen(false);
          }}
          onConfirm={(reason) => {
            setReviewOpen(false);
            setPreparedReason(reason);
          }}
          title={t("Trial conclusion impact review")}
        />
      ) : null}
    </article>
  );
}
