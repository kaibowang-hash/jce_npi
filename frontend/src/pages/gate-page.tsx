import { useState } from "react";

import type { Scenario } from "../domain/view-models";
import { activities } from "../fixtures/prototype";
import { formatDate } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button } from "../ui-adapters/npi-ui";
import {
  DockedInspector,
  ObjectHeader,
  SectionAnchors,
} from "../components/object-components";
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

export default function GatePage({
  scenario,
  navigate,
  qualityFailure,
}: {
  scenario: Scenario;
  navigate: (target: string) => void;
  qualityFailure: boolean;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const [reviewOpen, setReviewOpen] = useState(false);
  const [preparedReason, setPreparedReason] = useState<string | null>(null);
  const gateCode = qualityFailure ? "G6" : "G5";
  const gateName = qualityFailure
    ? t("NPI readiness review")
    : t("Sample approval review");
  return (
    <article className="page page--object">
      <ObjectHeader
        code={`${gateCode} / PJ-26018`}
        metadata={
          <span>
            {t("Review date")}:{" "}
            <time dateTime="2026-07-24">
              {formatDate(locale, "2026-07-24")}
            </time>{" "}
            · {t("Decision version")}:{" "}
            <span data-language-exempt="identifier">v3</span>
          </span>
        }
        name={gateName}
        nameIsBusinessData={false}
        primaryAction={{
          disabled: scenario === "read_only",
          label: t("Review impact and decide"),
          onClick: () => {
            setReviewOpen(true);
          },
        }}
        source={source}
        status={
          <SemanticStatus
            label={
              qualityFailure
                ? t("Blocked by formal quality result")
                : t("Blocked by missing evidence")
            }
            tone="danger"
          />
        }
      />
      <SectionAnchors
        sections={[
          { id: "gate-deliverables", label: t("Deliverables and evidence") },
          { id: "gate-evidence", label: t("Selected evidence") },
          { id: "gate-decision", label: t("Review decision") },
        ]}
      />
      {preparedReason ? (
        <div className="scenario-banner scenario-banner--queued" role="status">
          <span>
            {t("Prototype command prepared. No gate decision was saved.")}
          </span>
          <span>
            {t(
              "The in-memory prototype command captured a reason; no audit record was persisted.",
            )}
          </span>
        </div>
      ) : null}
      <div className="review-layout">
        <Panel id="gate-deliverables" title={t("Deliverables and evidence")}>
          <ul className="evidence-tree">
            <li>
              <SemanticStatus
                label={t("Product baseline B02")}
                tone="success"
              />
              <small>{t("Released and immutable")}</small>
            </li>
            <li>
              <SemanticStatus
                label={t("Tooling design revision C")}
                tone="success"
              />
              <small>{t("Released for trial")}</small>
            </li>
            <li>
              <SemanticStatus
                label={t("T1 dimensional report")}
                tone="danger"
              />
              <small>{t("Missing approved version")}</small>
            </li>
            <li>
              <SemanticStatus
                label={t("Formal quality result")}
                tone={qualityFailure ? "danger" : "warning"}
              />
              <small>
                {qualityFailure
                  ? t("Failed in ERPNext")
                  : t("Pending in ERPNext")}
              </small>
            </li>
            <li>
              <SemanticStatus
                label={t("Customer sample approval")}
                tone="warning"
              />
              <small>{t("Pending customer decision")}</small>
            </li>
          </ul>
          <Button
            onClick={() => {
              navigate("/projects/PJ-26018");
            }}
          >
            {t("Return to project")}
          </Button>
        </Panel>
        <Panel id="gate-evidence" title={t("Selected evidence")}>
          <div className="evidence-preview">
            <div
              className="document-placeholder"
              aria-label={t("Document preview")}
            >
              <span data-language-exempt="identifier">T1-DIM-REPORT.pdf</span>
            </div>
            <DefinitionList
              rows={[
                { label: t("Revision"), value: "A", exempt: "identifier" },
                {
                  label: t("Evidence state"),
                  value: t("Draft, approval missing"),
                },
                {
                  label: t("File hash"),
                  value: "sha256:3f8c…91b2",
                  exempt: "identifier",
                },
                {
                  label: t("Referenced trial"),
                  value: "T1",
                  exempt: "identifier",
                },
                {
                  label: t("Changed since last review"),
                  value: t("Yes, measurements were replaced"),
                },
              ]}
            />
          </div>
          <div className="blocking-message">
            <SemanticStatus label={t("Decision blocked")} tone="danger" />
            <p>
              {qualityFailure
                ? t(
                    "ERPNext reports a failed formal quality result. Readiness percentage cannot override this blocker.",
                  )
                : t(
                    "The dimensional report is not approved and two major defects remain open.",
                  )}
            </p>
          </div>
        </Panel>
        <DockedInspector
          activities={activities}
          id="gate-decision"
          title={t("Review decision")}
        >
          <DefinitionList
            rows={[
              {
                label: t("Decision options"),
                value: t("Pass, conditional pass, reject, or reopen"),
              },
              {
                label: t("Evidence snapshot"),
                value: t("{{count}} exact versions", { count: 5 }),
              },
              { label: t("Open blockers"), value: qualityFailure ? 2 : 3 },
              { label: t("Changed inputs"), value: 1 },
              { label: t("Required permission"), value: t("Gate approver") },
            ]}
          />
          <p className="context-help">
            {t(
              "Why blocked: Gate decisions freeze exact evidence versions. Missing or failed formal evidence cannot be replaced by a score.",
            )}
          </p>
        </DockedInspector>
      </div>
      {reviewOpen ? (
        <ImpactReview
          confirmLabel={t("Prepare decision command")}
          details={{
            objectIdentity: `${gateCode} / PJ-26018`,
            version: "v3 · snapshot pending",
            impact: t(
              "The decision will lock five evidence versions and affect the next two Gates.",
            ),
            permission: t("Gate approver permission is required."),
            irreversible: t(
              "The historical decision snapshot cannot be overwritten.",
            ),
            failureHandling: t(
              "A failed command changes nothing and returns a trace ID.",
            ),
            audit: t(
              "A submitted command would record the actor, reason, versions, result, and trace ID.",
            ),
          }}
          onCancel={() => {
            setReviewOpen(false);
          }}
          onConfirm={(reason) => {
            setReviewOpen(false);
            setPreparedReason(reason);
          }}
          title={t("Gate decision impact review")}
        />
      ) : null}
    </article>
  );
}
