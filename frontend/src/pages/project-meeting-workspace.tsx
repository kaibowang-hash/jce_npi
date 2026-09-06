import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type {
  CollaborationDataSource,
  MeetingMinute,
  MeetingMinuteCollection,
  MeetingMinuteDraft,
} from "../api/collaboration-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { ReportWorkspaceDirty } from "../app/workspace-navigation";
import { RequestFailurePanel } from "../components/problem-details-panel";
import { ImpactReview, Panel, SemanticStatus } from "../components/primitives";
import { formatDateTime, formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

type State =
  | { kind: "loading" }
  | { kind: "loaded"; value: MeetingMinuteCollection }
  | { kind: "failed"; failure: RequestFailure };

const standardTemplate = {
  globalId: "00000000-0000-4000-8000-000000000902",
  version: 1,
  snapshotHash:
    "6e8cdc80e514c8cd594d780bb8251a35a0b415e649a7ac529b77b1b9917a6a4c",
} as const;

function initialDateTime(): string {
  const now = new Date();
  now.setSeconds(0, 0);
  return now.toISOString().slice(0, 16);
}

function meetingKindLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: "action" | "decision_request",
): string {
  return value === "action" ? t("Action item") : t("Decision request");
}

function MeetingList({
  meetings,
  navigate,
}: {
  meetings: readonly MeetingMinute[];
  navigate: (target: string) => void;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  if (!meetings.length)
    return (
      <div className="table-empty">
        {t("No meeting minutes have been recorded for this Project.")}
      </div>
    );
  return (
    <div className="meeting-minute-list">
      {meetings.map((meeting) => (
        <article key={meeting.globalId}>
          <header className="meeting-minute-list__header">
            <div>
              <h3 data-language-exempt="business-data">{meeting.title}</h3>
              <small>
                {formatDateTime(locale, meeting.occurredAt)} ·{" "}
                {t("{{count}} attendees", {
                  count: meeting.attendeeUserIds.length,
                })}
              </small>
            </div>
            <SemanticStatus label={t("Immutable")} tone="info" />
          </header>
          <dl>
            <div>
              <dt>{t("Agenda")}</dt>
              <dd data-language-exempt="business-data">
                {meeting.sections.agenda}
              </dd>
            </div>
            <div>
              <dt>{t("Discussion")}</dt>
              <dd data-language-exempt="business-data">
                {meeting.sections.discussion}
              </dd>
            </div>
            <div>
              <dt>{t("Decisions")}</dt>
              <dd data-language-exempt="business-data">
                {meeting.sections.decisions}
              </dd>
            </div>
          </dl>
          <footer className="meeting-minute-list__footer">
            <span>
              {t("{{count}} linked work items", {
                count: meeting.linkedItems.length,
              })}
            </span>
            {meeting.linkedItems.map((item) => (
              <Button
                key={item.workItemId}
                onClick={() => {
                  navigate(item.targetRoute);
                }}
                visual="ghost"
              >
                {meetingKindLabel(t, item.kind)} ·{" "}
                <span data-language-exempt="business-data">{item.title}</span>
              </Button>
            ))}
          </footer>
        </article>
      ))}
    </div>
  );
}

export function ProjectMeetingWorkspace({
  dataSource,
  navigate,
  projectId,
  reportWorkspaceDirty,
}: {
  dataSource?: CollaborationDataSource | undefined;
  navigate: (target: string) => void;
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);
  const [state, setState] = useState<State>({ kind: "loading" });
  const [title, setTitle] = useState("");
  const [occurredAt, setOccurredAt] = useState(initialDateTime);
  const [attendees, setAttendees] = useState(
    sessionCommandContext?.userId ?? "",
  );
  const [agenda, setAgenda] = useState("");
  const [discussion, setDiscussion] = useState("");
  const [decisions, setDecisions] = useState("");
  const [workTitle, setWorkTitle] = useState("");
  const [workOwner, setWorkOwner] = useState(
    sessionCommandContext?.userId ?? "",
  );
  const [workDueAt, setWorkDueAt] = useState(initialDateTime);
  const [workKind, setWorkKind] = useState<"action" | "decision_request">(
    "action",
  );
  const [reviewOpen, setReviewOpen] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [commandFailure, setCommandFailure] = useState<RequestFailure | null>(
    null,
  );
  const [created, setCreated] = useState<MeetingMinute | null>(null);
  const dirty = Boolean(
    title || agenda || discussion || decisions || workTitle,
  );
  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    reportWorkspaceDirty(
      dirty
        ? {
            objectIdentity: t("Meeting minute draft"),
            version: t("Unsaved"),
            returnFocusTarget: () => document.getElementById("meeting-title"),
          }
        : null,
    );
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [dirty, reportWorkspaceDirty, t]);
  useEffect(() => {
    if (!dataSource) return undefined;
    const controller = new AbortController();
    const current = generation.current + 1;
    generation.current = current;
    void dataSource
      .loadMeetings(projectId, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted && generation.current === current)
          setState({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && generation.current === current)
          setState({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, projectId]);
  const reset = useCallback(() => {
    setTitle("");
    setAgenda("");
    setDiscussion("");
    setDecisions("");
    setWorkTitle("");
    setCreated(null);
    setCommandFailure(null);
  }, []);
  const draft = useMemo<MeetingMinuteDraft | null>(() => {
    const attendeeUserIds = attendees
      .split(",")
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean);
    if (
      !title.trim() ||
      !agenda.trim() ||
      !discussion.trim() ||
      !decisions.trim() ||
      !attendeeUserIds.length
    )
      return null;
    const occurred = new Date(occurredAt);
    if (Number.isNaN(occurred.getTime())) return null;
    const due = new Date(workDueAt);
    if (workTitle.trim() && (Number.isNaN(due.getTime()) || !workOwner.trim()))
      return null;
    const items = workTitle.trim()
      ? [
          {
            itemKey: "meeting-item-1",
            kind: workKind,
            title: workTitle.trim(),
            detail: null,
            ownerUserId: workOwner.trim().toLowerCase(),
            dueAt: due.toISOString(),
            severity: "medium" as const,
            blocking: false,
          },
        ]
      : [];
    return {
      templateRef: standardTemplate,
      title: title.trim(),
      occurredAt: occurred.toISOString(),
      attendeeUserIds,
      sections: {
        agenda: agenda.trim(),
        discussion: discussion.trim(),
        decisions: decisions.trim(),
      },
      items,
    };
  }, [
    agenda,
    attendees,
    decisions,
    discussion,
    occurredAt,
    title,
    workDueAt,
    workKind,
    workOwner,
    workTitle,
  ]);
  const create = (): void => {
    if (
      !dataSource ||
      state.kind !== "loaded" ||
      !draft ||
      !sessionCommandContext
    )
      return;
    const controller = new AbortController();
    setProcessing(true);
    setCommandFailure(null);
    void dataSource
      .createMeeting(projectId, state.value.projectVersion, draft, {
        csrfToken: sessionCommandContext.csrfToken,
        idempotencyKey: `meeting-minute-${globalThis.crypto.randomUUID()}`,
        signal: controller.signal,
      })
      .then((meeting) => {
        setCreated(meeting);
        setState((current) =>
          current.kind === "loaded"
            ? {
                kind: "loaded",
                value: {
                  ...current.value,
                  projectVersion:
                    meeting.projectVersion ?? current.value.projectVersion,
                  items: [meeting, ...current.value.items],
                },
              }
            : current,
        );
        setTitle("");
        setAgenda("");
        setDiscussion("");
        setDecisions("");
        setWorkTitle("");
      })
      .catch((error: unknown) => {
        setCommandFailure(toRequestFailure(error));
      })
      .finally(() => {
        setProcessing(false);
      });
  };
  if (!dataSource)
    return (
      <section className="workspace-resource-state" role="status">
        <SemanticStatus label={t("Unavailable")} tone="warning" />
        <p>{t("The live meeting-minute data source is not configured.")}</p>
      </section>
    );
  if (state.kind === "loading")
    return (
      <section
        aria-busy="true"
        className="workspace-resource-state"
        role="status"
      >
        {t("Loading meeting minutes")}
      </section>
    );
  if (state.kind === "failed")
    return (
      <section className="workspace-resource-state" role="alert">
        <SemanticStatus label={t("Unavailable")} tone="danger" />
        <p>{t("Meeting minutes are unavailable.")}</p>
        <RequestFailurePanel failure={state.failure} />
        <Button
          icon="refresh"
          onClick={() => {
            setAttempt((value) => value + 1);
          }}
        >
          {t("Retry")}
        </Button>
      </section>
    );
  return (
    <div className="project-meeting-workspace">
      {created ? (
        <div className="utility-message" role="status">
          <SemanticStatus label={t("Created")} tone="success" />
          <span>
            {t(
              "The immutable meeting minute and {{count}} linked work items were created.",
              { count: created.linkedItems.length },
            )}
          </span>
        </div>
      ) : null}
      {commandFailure ? (
        <div role="alert">
          <p>{t("The meeting minute was not created.")}</p>
          <RequestFailurePanel failure={commandFailure} />
        </div>
      ) : null}
      <div className="engineering-layout engineering-layout--meeting">
        <Panel title={t("Meeting minutes")} scrollableBody>
          <MeetingList meetings={state.value.items} navigate={navigate} />
        </Panel>
        <Panel title={t("Record meeting minute")}>
          {state.value.permissions.canAdminister ? (
            <form
              className="meeting-minute-form"
              onSubmit={(event) => {
                event.preventDefault();
                if (draft) setReviewOpen(true);
              }}
            >
              <label>
                <span>{t("Meeting title")}</span>
                <TextInput
                  id="meeting-title"
                  maxLength={280}
                  onChange={(event) => {
                    setTitle(event.currentTarget.value);
                  }}
                  required
                  value={title}
                />
              </label>
              <label>
                <span>{t("Meeting time")}</span>
                <TextInput
                  onChange={(event) => {
                    setOccurredAt(event.currentTarget.value);
                  }}
                  required
                  type="datetime-local"
                  value={occurredAt}
                />
              </label>
              <label>
                <span>{t("Attendee emails")}</span>
                <TextInput
                  onChange={(event) => {
                    setAttendees(event.currentTarget.value);
                  }}
                  required
                  value={attendees}
                />
              </label>
              <label>
                <span>{t("Agenda")}</span>
                <textarea
                  maxLength={8000}
                  onChange={(event) => {
                    setAgenda(event.currentTarget.value);
                  }}
                  required
                  rows={3}
                  value={agenda}
                />
              </label>
              <label>
                <span>{t("Discussion")}</span>
                <textarea
                  maxLength={8000}
                  onChange={(event) => {
                    setDiscussion(event.currentTarget.value);
                  }}
                  required
                  rows={3}
                  value={discussion}
                />
              </label>
              <label>
                <span>{t("Decisions")}</span>
                <textarea
                  maxLength={8000}
                  onChange={(event) => {
                    setDecisions(event.currentTarget.value);
                  }}
                  required
                  rows={3}
                  value={decisions}
                />
              </label>
              <fieldset>
                <legend>{t("Optional linked work item")}</legend>
                <label>
                  <span>{t("Work item title")}</span>
                  <TextInput
                    maxLength={280}
                    onChange={(event) => {
                      setWorkTitle(event.currentTarget.value);
                    }}
                    value={workTitle}
                  />
                </label>
                <label>
                  <span>{t("Work item type")}</span>
                  <Select
                    onChange={(event) => {
                      setWorkKind(
                        event.currentTarget.value as
                          | "action"
                          | "decision_request",
                      );
                    }}
                    value={workKind}
                  >
                    <option value="action">{t("Action item")}</option>
                    <option value="decision_request">
                      {t("Decision request")}
                    </option>
                  </Select>
                </label>
                <label>
                  <span>{t("Owner email")}</span>
                  <TextInput
                    inputMode="email"
                    onChange={(event) => {
                      setWorkOwner(event.currentTarget.value);
                    }}
                    value={workOwner}
                  />
                </label>
                <label>
                  <span>{t("Due time")}</span>
                  <TextInput
                    onChange={(event) => {
                      setWorkDueAt(event.currentTarget.value);
                    }}
                    type="datetime-local"
                    value={workDueAt}
                  />
                </label>
              </fieldset>
              {!sessionCommandContext ? (
                <p>
                  {t(
                    "The authenticated session is not ready. Reconcile the session before creating a record.",
                  )}
                </p>
              ) : null}
              <div className="detail-actions">
                <Button
                  disabled={!draft || !sessionCommandContext || processing}
                  type="submit"
                  visual="primary"
                >
                  {processing ? t("Creating") : t("Review and create")}
                </Button>
                <Button type="button" onClick={reset}>
                  {t("Clear")}
                </Button>
              </div>
            </form>
          ) : (
            <div className="scenario-banner scenario-banner--read_only">
              <SemanticStatus label={t("Read only")} tone="info" />
              <span>
                {t(
                  "Only Project administrators can create immutable meeting minutes.",
                )}
              </span>
            </div>
          )}
        </Panel>
      </div>
      {reviewOpen && draft ? (
        <ImpactReview
          title={t("Review meeting-minute command")}
          confirmLabel={t("Create meeting minute")}
          reasonRequired={false}
          onCancel={() => {
            setReviewOpen(false);
          }}
          onConfirm={() => {
            setReviewOpen(false);
            create();
          }}
          details={{
            objectIdentity: title,
            version: formatNumber(locale, state.value.projectVersion, 0),
            impact: t(
              "Creates one immutable meeting minute and {{count}} linked work items.",
              { count: draft.items.length },
            ),
            permission: t("Project administration permission is required."),
            irreversible: t(
              "The meeting minute cannot be edited or deleted after creation.",
            ),
            failureHandling: t(
              "A failed transaction creates neither the minute nor linked work items. Retry uses a new command identity.",
            ),
            audit: t(
              "The actor, Project version, template, content hash and linked work are audited.",
            ),
          }}
        />
      ) : null}
    </div>
  );
}
