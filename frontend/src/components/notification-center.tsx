import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type {
  CollaborationDataSource,
  InternalNotification,
  InternalNotificationCollection,
  NotificationKind,
  NotificationPreference,
  OptionalEmailNotificationKind,
} from "../api/collaboration-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import type { SessionCommandContext } from "../i18n/runtime";
import { formatDateTime } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button } from "../ui-adapters/npi-ui";
import { RequestFailurePanel } from "./problem-details-panel";
import { SemanticStatus } from "./primitives";

type FeedState =
  | { kind: "loading" }
  | { kind: "loaded"; value: InternalNotificationCollection }
  | { kind: "failed"; failure: RequestFailure };
type PreferenceState =
  | { kind: "loading" }
  | {
      kind: "loaded";
      value: NotificationPreference;
      selected: readonly OptionalEmailNotificationKind[];
    }
  | { kind: "failed"; failure: RequestFailure };

const optionalKinds: readonly OptionalEmailNotificationKind[] = [
  "due_reminder",
  "overdue_escalation",
  "gate_attention",
];

function notificationTitle(
  t: ReturnType<typeof useI18n>["t"],
  kind: NotificationKind,
): string {
  switch (kind) {
    case "due_reminder":
      return t("Work item due soon");
    case "overdue_escalation":
      return t("Work item overdue");
    case "critical_blocker":
      return t("Critical blocker requires attention");
    case "gate_attention":
      return t("Gate review requires attention");
  }
}

function emailKindLabel(
  t: ReturnType<typeof useI18n>["t"],
  kind: OptionalEmailNotificationKind,
): string {
  switch (kind) {
    case "due_reminder":
      return t("Due reminders by email");
    case "overdue_escalation":
      return t("Overdue escalations by email");
    case "gate_attention":
      return t("Gate attention by email");
  }
}

function deliveryLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: InternalNotification["emailDeliveryState"],
): string {
  switch (value) {
    case "not_requested":
      return t("Email not requested");
    case "queued":
      return t("Email queued");
    case "failed":
      return t("Email failed");
    case "unavailable":
      return t("Email unavailable");
  }
}

export function NotificationCenter({
  dataSource,
  navigate,
  session,
}: {
  dataSource: CollaborationDataSource;
  navigate: (target: string) => void;
  session: SessionCommandContext | null;
}): React.JSX.Element {
  const { locale, t } = useI18n();
  const [open, setOpen] = useState(false);
  const [feed, setFeed] = useState<FeedState>({ kind: "loading" });
  const [preference, setPreference] = useState<PreferenceState>({
    kind: "loading",
  });
  const [saving, setSaving] = useState(false);
  const request = useRef<AbortController | null>(null);
  const refresh = useCallback((): void => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setFeed({ kind: "loading" });
    setPreference({ kind: "loading" });
    void Promise.allSettled([
      dataSource.loadNotifications(false, undefined, controller.signal),
      dataSource.loadPreference(controller.signal),
    ]).then(([feedResult, preferenceResult]) => {
      if (controller.signal.aborted) return;
      setFeed(
        feedResult.status === "fulfilled"
          ? { kind: "loaded", value: feedResult.value }
          : { kind: "failed", failure: toRequestFailure(feedResult.reason) },
      );
      setPreference(
        preferenceResult.status === "fulfilled"
          ? {
              kind: "loaded",
              value: preferenceResult.value,
              selected: preferenceResult.value.emailKinds,
            }
          : {
              kind: "failed",
              failure: toRequestFailure(preferenceResult.reason),
            },
      );
    });
  }, [dataSource]);
  useEffect(() => {
    queueMicrotask(refresh);
    return () => request.current?.abort();
  }, [refresh]);
  const unreadCount = useMemo(
    () =>
      feed.kind === "loaded"
        ? feed.value.items.filter((item) => item.readAt === null).length
        : 0,
    [feed],
  );
  const markRead = (item: InternalNotification): void => {
    if (!session || item.readAt !== null) return;
    const controller = new AbortController();
    void dataSource
      .markNotificationRead(item, {
        csrfToken: session.csrfToken,
        idempotencyKey: `notification-read-${item.globalId}`,
        signal: controller.signal,
      })
      .then((updated) => {
        setFeed((current) =>
          current.kind === "loaded"
            ? {
                kind: "loaded",
                value: {
                  ...current.value,
                  items: current.value.items.map((candidate) =>
                    candidate.globalId === updated.globalId
                      ? updated
                      : candidate,
                  ),
                },
              }
            : current,
        );
      })
      .catch((error: unknown) => {
        setFeed({ kind: "failed", failure: toRequestFailure(error) });
      });
  };
  const savePreference = (): void => {
    if (!session || preference.kind !== "loaded") return;
    const controller = new AbortController();
    setSaving(true);
    void dataSource
      .savePreference(preference.value, preference.selected, {
        csrfToken: session.csrfToken,
        idempotencyKey: `notification-preference-${globalThis.crypto.randomUUID()}`,
        signal: controller.signal,
      })
      .then((value) => {
        setPreference({ kind: "loaded", value, selected: value.emailKinds });
      })
      .catch((error: unknown) => {
        setPreference({ kind: "failed", failure: toRequestFailure(error) });
      })
      .finally(() => {
        setSaving(false);
      });
  };
  return (
    <div className="notification-center">
      <Button
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={t("Notifications")}
        icon="alarm"
        onClick={() => {
          setOpen((value) => !value);
        }}
        visual="ghost"
      >
        {t("{{count}} notifications", { count: unreadCount })}
      </Button>
      {open ? (
        <section
          aria-label={t("Notifications")}
          className="notification-center__panel"
          role="dialog"
        >
          <header className="notification-center__header">
            <div className="notification-center__header-copy">
              <strong>{t("Notifications")}</strong>
              <small>{t("Recipient-filtered internal feed")}</small>
            </div>
            <Button
              aria-label={t("Close notifications")}
              icon="clear"
              onClick={() => {
                setOpen(false);
              }}
              visual="ghost"
            />
          </header>
          {feed.kind === "loading" ? (
            <p aria-busy="true">{t("Loading notifications")}</p>
          ) : feed.kind === "failed" ? (
            <div role="alert">
              <p>{t("Notifications are unavailable.")}</p>
              <RequestFailurePanel failure={feed.failure} />
              <Button icon="refresh" onClick={refresh}>
                {t("Retry")}
              </Button>
            </div>
          ) : feed.value.items.length ? (
            <ul className="notification-center__list">
              {feed.value.items.map((item) => (
                <li
                  className={`notification-center__entry${item.readAt === null ? " is-unread" : ""}`}
                  key={item.globalId}
                >
                  <button
                    className="notification-center__item"
                    onClick={() => {
                      markRead(item);
                      setOpen(false);
                      navigate(item.targetRoute);
                    }}
                    type="button"
                  >
                    <span className="notification-center__item-copy">
                      <strong>{notificationTitle(t, item.kind)}</strong>
                      <small>
                        {t("Due {{time}}", {
                          time: formatDateTime(locale, item.sourceDueAt),
                        })}
                      </small>
                      <small>{deliveryLabel(t, item.emailDeliveryState)}</small>
                    </span>
                    {item.criticalAudit ? (
                      <SemanticStatus
                        label={t("Critical audit")}
                        tone="danger"
                      />
                    ) : item.readAt === null ? (
                      <SemanticStatus label={t("Unread")} tone="info" />
                    ) : (
                      <SemanticStatus label={t("Read")} />
                    )}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p>{t("No notifications are available.")}</p>
          )}
          <section
            className="notification-center__preferences"
            aria-label={t("Email notification preferences")}
          >
            <h3>{t("Email notification preferences")}</h3>
            {preference.kind === "loading" ? (
              <p aria-busy="true">{t("Loading notification preferences")}</p>
            ) : preference.kind === "failed" ? (
              <RequestFailurePanel failure={preference.failure} />
            ) : (
              <>
                {optionalKinds.map((kind) => (
                  <label key={kind}>
                    <input
                      checked={preference.selected.includes(kind)}
                      onChange={(event) => {
                        setPreference({
                          ...preference,
                          selected: event.currentTarget.checked
                            ? [...preference.selected, kind]
                            : preference.selected.filter(
                                (item) => item !== kind,
                              ),
                        });
                      }}
                      type="checkbox"
                    />
                    {emailKindLabel(t, kind)}
                  </label>
                ))}
                <label>
                  <input checked disabled type="checkbox" />
                  {t("Critical audit email is mandatory")}
                </label>
                <Button disabled={!session || saving} onClick={savePreference}>
                  {saving ? t("Saving") : t("Save preferences")}
                </Button>
              </>
            )}
          </section>
        </section>
      ) : null}
    </div>
  );
}
