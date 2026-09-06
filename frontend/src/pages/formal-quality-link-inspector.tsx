import { useEffect, useRef, useState } from "react";

import {
  LiveFormalQualityLinkDataSource,
  type FormalQualityCandidate,
  type FormalQualityLinkCollection,
  type FormalQualityLinkDataSource,
  type FormalQualityLinkItem,
  type FormalQualitySourceReference,
} from "../api/formal-quality-link-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { ImpactReview, Panel, SemanticStatus } from "../components/primitives";
import { RequestFailurePanel } from "../components/problem-details-panel";
import { useI18n } from "../i18n/runtime";
import { Button } from "../ui-adapters/npi-ui";

type ResourceState =
  | { kind: "loading" }
  | {
      kind: "loaded";
      collection: FormalQualityLinkCollection;
      candidate: FormalQualityCandidate | null;
    }
  | { kind: "failed"; failure: RequestFailure };

type CommandState =
  | { kind: "idle" }
  | { kind: "processing" }
  | { kind: "succeeded"; item: FormalQualityLinkItem }
  | { kind: "failed"; failure: RequestFailure };

const liveDataSource = new LiveFormalQualityLinkDataSource();

function sourceItem(
  collection: FormalQualityLinkCollection,
  source: FormalQualitySourceReference,
): FormalQualityLinkItem | null {
  const matches = collection.items.filter(
    (item) =>
      item.linkHead.sourceKind === source.sourceKind &&
      item.linkHead.sourceGlobalId === source.sourceGlobalId,
  );
  return matches.length === 1 ? (matches[0] ?? null) : null;
}

function stateLabel(
  t: (source: string, values?: Record<string, string | number>) => string,
  item: FormalQualityLinkItem | null,
  candidate: FormalQualityCandidate | null,
): string {
  if (item?.reconciliation.state === "current")
    return t("Current formal quality link");
  if (item?.reconciliation.state === "drifted")
    return t("Drifted formal quality link");
  if (item?.reconciliation.state === "unavailable")
    return t("Formal quality truth unavailable");
  if (candidate) return t("Formal quality reference available");
  return t("No formal quality reference available");
}

export function FormalQualityLinkInspector({
  dataSource = liveDataSource,
  projectId,
  source,
}: {
  readonly dataSource?: FormalQualityLinkDataSource | undefined;
  readonly projectId: string;
  readonly source: FormalQualitySourceReference;
}): React.JSX.Element {
  const { sessionCommandContext, t } = useI18n();
  const [resource, setResource] = useState<ResourceState>({ kind: "loading" });
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const [reviewOpen, setReviewOpen] = useState(false);
  const returnFocus = useRef<HTMLElement | null>(null);
  const {
    scopeGlobalId,
    scopeKind,
    sourceCapability,
    sourceGlobalId,
    sourceKind,
    sourceSnapshotHash,
    sourceVersion,
  } = source;

  useEffect(() => {
    const controller = new AbortController();
    const requestedSource: FormalQualitySourceReference = {
      scopeGlobalId,
      scopeKind,
      sourceCapability,
      sourceGlobalId,
      sourceKind,
      sourceSnapshotHash,
      sourceVersion,
    };
    void dataSource
      .load(projectId, requestedSource, controller.signal)
      .then(({ collection, candidate }) => {
        if (!controller.signal.aborted)
          setResource({ kind: "loaded", collection, candidate });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setResource({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [
    dataSource,
    projectId,
    scopeGlobalId,
    scopeKind,
    sourceCapability,
    sourceGlobalId,
    sourceKind,
    sourceSnapshotHash,
    sourceVersion,
  ]);

  if (resource.kind === "loading")
    return (
      <Panel
        className="formal-quality-link"
        title={t("Formal quality reference")}
      >
        <div className="formal-quality-link__state" role="status">
          <SemanticStatus
            label={t("Loading formal quality truth")}
            tone="neutral"
          />
        </div>
      </Panel>
    );
  if (resource.kind === "failed")
    return (
      <Panel
        className="formal-quality-link"
        title={t("Formal quality reference")}
      >
        <RequestFailurePanel failure={resource.failure} />
      </Panel>
    );

  const item = sourceItem(resource.collection, source);
  const canLink = Boolean(
    resource.collection.permissions.link &&
    source.sourceCapability &&
    resource.candidate &&
    sessionCommandContext &&
    command.kind !== "processing",
  );
  const expectedLinkHeadVersion = item?.linkHead.optimisticVersion ?? 0;

  const execute = (): void => {
    if (!canLink || !resource.candidate || !sessionCommandContext) return;
    const controller = new AbortController();
    setCommand({ kind: "processing" });
    void dataSource
      .link(
        projectId,
        { source, candidate: resource.candidate, expectedLinkHeadVersion },
        {
          csrfToken: sessionCommandContext.csrfToken,
          idempotencyKey: `formal-quality-link-${globalThis.crypto.randomUUID()}`,
          signal: controller.signal,
        },
      )
      .then((nextItem) => {
        setResource({
          kind: "loaded",
          collection: {
            ...resource.collection,
            items: [
              ...resource.collection.items.filter(
                (candidate) =>
                  candidate.linkHead.sourceKind !== source.sourceKind ||
                  candidate.linkHead.sourceGlobalId !== source.sourceGlobalId,
              ),
              nextItem,
            ],
          },
          candidate: resource.candidate,
        });
        setCommand({ kind: "succeeded", item: nextItem });
      })
      .catch((error: unknown) => {
        setCommand({ kind: "failed", failure: toRequestFailure(error) });
      });
  };

  return (
    <Panel
      className="formal-quality-link"
      title={t("Formal quality reference")}
    >
      <div
        className="formal-quality-link__state"
        data-testid="formal-quality-link-state"
        role="status"
      >
        <SemanticStatus
          label={stateLabel(t, item, resource.candidate)}
          tone={
            item?.reconciliation.state === "current"
              ? "success"
              : item?.reconciliation.state === "drifted"
                ? "warning"
                : "neutral"
          }
        />
        <p>
          {t(
            "Raw ERPNext quality codes remain observed truth and are never interpreted as a pass.",
          )}
        </p>
      </div>

      {item ? (
        <dl className="formal-quality-link__facts">
          <div className="formal-quality-link__fact">
            <dt>{t("Reconciliation")}</dt>
            <dd>{stateLabel(t, item, resource.candidate)}</dd>
          </div>
          <div className="formal-quality-link__fact">
            <dt>{t("Formal record kind")}</dt>
            <dd data-language-exempt="business-data">
              {item.linkRevision.formalObservation.recordKind}
            </dd>
          </div>
          <div className="formal-quality-link__fact">
            <dt>{t("Raw status code")}</dt>
            <dd data-language-exempt="business-data">
              {item.linkRevision.formalObservation.statusCode}
            </dd>
          </div>
          <div className="formal-quality-link__fact">
            <dt>{t("Raw result code")}</dt>
            <dd data-language-exempt="business-data">
              {item.linkRevision.formalObservation.resultCode ?? "—"}
            </dd>
          </div>
        </dl>
      ) : resource.candidate ? (
        <p>
          {t(
            "One fresh authoritative formal quality observation is available to link.",
          )}
        </p>
      ) : (
        <p>
          {t(
            "No fresh authoritative formal quality observation is available for this exact source.",
          )}
        </p>
      )}

      {!source.sourceCapability || !resource.collection.permissions.link ? (
        <p className="formal-quality-link__notice" role="status">
          {t(
            "This formal quality reference is read only in the current Project context.",
          )}
        </p>
      ) : null}
      {command.kind === "processing" ? (
        <p className="formal-quality-link__notice" role="status">
          {t("Linking the exact formal quality reference.")}
        </p>
      ) : null}
      {command.kind === "succeeded" ? (
        <p className="formal-quality-link__notice" role="status">
          {t("The exact formal quality reference is linked and audited.")}
        </p>
      ) : null}
      {command.kind === "failed" ? (
        <RequestFailurePanel failure={command.failure} />
      ) : null}

      {canLink ? (
        <Button
          onClick={(event) => {
            returnFocus.current = event.currentTarget;
            setReviewOpen(true);
          }}
          visual="primary"
        >
          {t("Link formal quality reference")}
        </Button>
      ) : null}

      {reviewOpen && resource.candidate ? (
        <ImpactReview
          confirmLabel={t("Link formal quality reference")}
          contextRows={[
            {
              label: t("Formal record kind"),
              value: resource.candidate.values.recordKind,
              exempt: "business-data",
            },
            {
              label: t("Raw status code"),
              value: resource.candidate.values.statusCode,
              exempt: "business-data",
            },
            {
              label: t("Raw result code"),
              value: resource.candidate.values.resultCode ?? "—",
              exempt: "business-data",
            },
          ]}
          details={{
            audit: t(
              "The exact source, projection head, observation, actor and trace are retained.",
            ),
            failureHandling: t(
              "A conflict or unavailable source creates no partial link revision.",
            ),
            impact: t(
              "Links one exact observed ERPNext quality reference to this internal source.",
            ),
            irreversible: t(
              "The retained link revision is immutable; a correction appends a successor.",
            ),
            objectIdentity: source.sourceGlobalId,
            permission: t(
              "The server requires exact Project and source-workspace authority.",
            ),
            version: t("Source version {{version}}", {
              version: source.sourceVersion,
            }),
          }}
          onCancel={() => {
            setReviewOpen(false);
          }}
          onConfirm={() => {
            setReviewOpen(false);
            execute();
          }}
          reasonRequired={false}
          returnFocusTarget={() => returnFocus.current}
          title={t("Review formal quality link")}
        />
      ) : null}
    </Panel>
  );
}
