import { NpiHttpClient, NpiTransportError } from "./http";
import type { ReportingPage } from "./reporting-data-source";

export type NotificationKind =
  | "due_reminder"
  | "overdue_escalation"
  | "critical_blocker"
  | "gate_attention";
export type OptionalEmailNotificationKind = Exclude<
  NotificationKind,
  "critical_blocker"
>;

export interface MeetingWorkItemDraft {
  itemKey: string;
  kind: "action" | "decision_request";
  title: string;
  detail: string | null;
  ownerUserId: string;
  dueAt: string;
  severity: "low" | "medium" | "high" | "critical";
  blocking: boolean;
}

export interface MeetingMinuteDraft {
  templateRef: { globalId: string; version: 1; snapshotHash: string };
  title: string;
  occurredAt: string;
  attendeeUserIds: readonly string[];
  sections: { agenda: string; discussion: string; decisions: string };
  items: readonly MeetingWorkItemDraft[];
}

export interface MeetingMinute {
  schemaVersion: 1;
  globalId: string;
  projectId: string;
  projectVersion?: number;
  templateRef: { globalId: string; version: 1; snapshotHash: string };
  title: string;
  occurredAt: string;
  attendeeUserIds: readonly string[];
  sections: { agenda: string; discussion: string; decisions: string };
  linkedItems: readonly {
    itemKey: string;
    kind: "action" | "decision_request";
    workItemId: string;
    title: string;
    ownerUserId: string;
    dueAt: string;
    targetRoute: string;
  }[];
  contentHash: string;
  createdBy: string;
  createdAt: string;
  version: 1;
}

export interface MeetingMinuteCollection {
  schemaVersion: 1;
  projectId: string;
  projectVersion: number;
  items: readonly MeetingMinute[];
  permissions: {
    canView: true;
    canContribute: boolean;
    canAdminister: boolean;
  };
}

export interface InternalNotification {
  schemaVersion: 1;
  globalId: string;
  projectId: string;
  source: {
    type:
      | "domain_work_item"
      | "gate_review_assignment"
      | "gate_review_invalidation";
    globalId: string;
    version: number;
  };
  kind: NotificationKind;
  criticalAudit: boolean;
  titleSource: string;
  messageParameters: { dueAt: string };
  targetRoute: string;
  sourceDueAt: string;
  emailDeliveryState: "not_requested" | "queued" | "failed" | "unavailable";
  failureCode: string | null;
  readAt: string | null;
  createdAt: string;
  version: number;
}

export interface InternalNotificationCollection {
  schemaVersion: 1;
  items: readonly InternalNotification[];
  page: ReportingPage;
  permissions: { serverFiltered: true };
}

export interface NotificationPreference {
  schemaVersion: 1;
  emailKinds: readonly OptionalEmailNotificationKind[];
  criticalAuditEmail: true;
  criticalAuditMutable: false;
  version: number;
}

export interface CollaborationCommandContext {
  csrfToken: string;
  idempotencyKey: string;
  signal: AbortSignal;
}

export interface CollaborationDataSource {
  loadMeetings(
    projectId: string,
    signal: AbortSignal,
  ): Promise<MeetingMinuteCollection>;
  createMeeting(
    projectId: string,
    expectedProjectVersion: number,
    draft: MeetingMinuteDraft,
    context: CollaborationCommandContext,
  ): Promise<MeetingMinute>;
  loadNotifications(
    unreadOnly: boolean,
    cursor: string | undefined,
    signal: AbortSignal,
  ): Promise<InternalNotificationCollection>;
  markNotificationRead(
    notification: InternalNotification,
    context: CollaborationCommandContext,
  ): Promise<InternalNotification>;
  loadPreference(signal: AbortSignal): Promise<NotificationPreference>;
  savePreference(
    preference: NotificationPreference,
    emailKinds: readonly OptionalEmailNotificationKind[],
    context: CollaborationCommandContext,
  ): Promise<NotificationPreference>;
}

const UUID =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const SHA = /^[a-f0-9]{64}$/u;
const EMAIL = /^[^\s@]+@[^\s@]+$/u;
const KEY = /^[a-z][a-z0-9_.-]{0,63}$/u;
const IDEMPOTENCY = /^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/u;
const NOTIFICATION_KINDS = new Set<NotificationKind>([
  "due_reminder",
  "overdue_escalation",
  "critical_blocker",
  "gate_attention",
]);
const EMAIL_KINDS = new Set<OptionalEmailNotificationKind>([
  "due_reminder",
  "overdue_escalation",
  "gate_attention",
]);

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exact(
  value: Record<string, unknown>,
  keys: readonly string[],
): boolean {
  return (
    Object.keys(value).length === keys.length &&
    keys.every((key) => Object.hasOwn(value, key))
  );
}

function text(value: unknown, maximum = 1024, minimum = 1): value is string {
  return (
    typeof value === "string" &&
    value.length >= minimum &&
    value.length <= maximum &&
    !Array.from(value).some((character) => {
      const code = character.charCodeAt(0);
      return code <= 31 || code === 127;
    })
  );
}

function integer(value: unknown, minimum = 0, maximum = 5000): value is number {
  return (
    Number.isSafeInteger(value) &&
    Number(value) >= minimum &&
    Number(value) <= maximum
  );
}

function dateTime(value: unknown): value is string {
  return text(value, 64) && !Number.isNaN(Date.parse(value));
}

function permissions(
  value: unknown,
): value is MeetingMinuteCollection["permissions"] {
  return (
    object(value) &&
    exact(value, ["canView", "canContribute", "canAdminister"]) &&
    value.canView === true &&
    typeof value.canContribute === "boolean" &&
    typeof value.canAdminister === "boolean"
  );
}

function templateRef(
  value: unknown,
): value is MeetingMinuteDraft["templateRef"] {
  return (
    object(value) &&
    exact(value, ["globalId", "version", "snapshotHash"]) &&
    value.globalId === "00000000-0000-4000-8000-000000000902" &&
    value.version === 1 &&
    text(value.snapshotHash, 64) &&
    SHA.test(value.snapshotHash)
  );
}

function sections(value: unknown): value is MeetingMinuteDraft["sections"] {
  return (
    object(value) &&
    exact(value, ["agenda", "discussion", "decisions"]) &&
    text(value.agenda, 8000) &&
    text(value.discussion, 8000) &&
    text(value.decisions, 8000)
  );
}

function linkedItem(value: unknown, projectId: string): boolean {
  const expectedRoutePrefix = `/projects/${projectId}/work?workItemId=`;
  return (
    object(value) &&
    exact(value, [
      "itemKey",
      "kind",
      "workItemId",
      "title",
      "ownerUserId",
      "dueAt",
      "targetRoute",
    ]) &&
    text(value.itemKey, 64) &&
    KEY.test(value.itemKey) &&
    (value.kind === "action" || value.kind === "decision_request") &&
    text(value.workItemId, 36) &&
    UUID.test(value.workItemId) &&
    text(value.title, 280) &&
    text(value.ownerUserId, 254) &&
    EMAIL.test(value.ownerUserId) &&
    dateTime(value.dueAt) &&
    text(value.targetRoute, 512) &&
    value.targetRoute === `${expectedRoutePrefix}${value.workItemId}`
  );
}

function meeting(value: unknown, projectId: string): value is MeetingMinute {
  if (!object(value)) return false;
  const required = [
    "schemaVersion",
    "globalId",
    "projectId",
    "templateRef",
    "title",
    "occurredAt",
    "attendeeUserIds",
    "sections",
    "linkedItems",
    "contentHash",
    "createdBy",
    "createdAt",
    "version",
  ];
  const keys = Object.keys(value);
  if (
    !keys.every((key) => [...required, "projectVersion"].includes(key)) ||
    !required.every((key) => Object.hasOwn(value, key))
  )
    return false;
  return (
    value.schemaVersion === 1 &&
    text(value.globalId, 36) &&
    UUID.test(value.globalId) &&
    value.projectId === projectId &&
    (value.projectVersion === undefined || integer(value.projectVersion, 1)) &&
    templateRef(value.templateRef) &&
    text(value.title, 280) &&
    dateTime(value.occurredAt) &&
    Array.isArray(value.attendeeUserIds) &&
    value.attendeeUserIds.length >= 1 &&
    value.attendeeUserIds.length <= 100 &&
    value.attendeeUserIds.every(
      (user) => text(user, 254) && EMAIL.test(user),
    ) &&
    new Set(value.attendeeUserIds).size === value.attendeeUserIds.length &&
    sections(value.sections) &&
    Array.isArray(value.linkedItems) &&
    value.linkedItems.length <= 50 &&
    value.linkedItems.every((item) => linkedItem(item, projectId)) &&
    text(value.contentHash, 64) &&
    SHA.test(value.contentHash) &&
    text(value.createdBy, 254) &&
    dateTime(value.createdAt) &&
    value.version === 1
  );
}

export function isMeetingMinuteCollection(
  value: unknown,
  projectId: string,
): value is MeetingMinuteCollection {
  return (
    object(value) &&
    exact(value, [
      "schemaVersion",
      "projectId",
      "projectVersion",
      "items",
      "permissions",
    ]) &&
    value.schemaVersion === 1 &&
    value.projectId === projectId &&
    integer(value.projectVersion, 1) &&
    Array.isArray(value.items) &&
    value.items.length <= 500 &&
    value.items.every((item) => meeting(item, projectId)) &&
    permissions(value.permissions)
  );
}

function notification(value: unknown): value is InternalNotification {
  if (
    !object(value) ||
    !exact(value, [
      "schemaVersion",
      "globalId",
      "projectId",
      "source",
      "kind",
      "criticalAudit",
      "titleSource",
      "messageParameters",
      "targetRoute",
      "sourceDueAt",
      "emailDeliveryState",
      "failureCode",
      "readAt",
      "createdAt",
      "version",
    ])
  )
    return false;
  const projectRoute = text(value.projectId, 36)
    ? `/projects/${value.projectId}`
    : "";
  return (
    value.schemaVersion === 1 &&
    text(value.globalId, 36) &&
    UUID.test(value.globalId) &&
    text(value.projectId, 36) &&
    UUID.test(value.projectId) &&
    object(value.source) &&
    exact(value.source, ["type", "globalId", "version"]) &&
    [
      "domain_work_item",
      "gate_review_assignment",
      "gate_review_invalidation",
    ].includes(String(value.source.type)) &&
    text(value.source.globalId, 36) &&
    UUID.test(value.source.globalId) &&
    integer(value.source.version, 1) &&
    NOTIFICATION_KINDS.has(value.kind as NotificationKind) &&
    typeof value.criticalAudit === "boolean" &&
    value.criticalAudit === (value.kind === "critical_blocker") &&
    text(value.titleSource, 140) &&
    object(value.messageParameters) &&
    exact(value.messageParameters, ["dueAt"]) &&
    dateTime(value.messageParameters.dueAt) &&
    text(value.targetRoute, 512) &&
    (value.targetRoute === projectRoute ||
      value.targetRoute.startsWith(`${projectRoute}/`) ||
      value.targetRoute.startsWith(`${projectRoute}?`)) &&
    !value.targetRoute.includes("//") &&
    dateTime(value.sourceDueAt) &&
    value.sourceDueAt === value.messageParameters.dueAt &&
    ["not_requested", "queued", "failed", "unavailable"].includes(
      String(value.emailDeliveryState),
    ) &&
    (value.failureCode === null || text(value.failureCode, 128)) &&
    (value.emailDeliveryState === "failed") === (value.failureCode !== null) &&
    (value.readAt === null || dateTime(value.readAt)) &&
    dateTime(value.createdAt) &&
    integer(value.version, 1)
  );
}

export function isInternalNotificationCollection(
  value: unknown,
): value is InternalNotificationCollection {
  return (
    object(value) &&
    exact(value, ["schemaVersion", "items", "page", "permissions"]) &&
    value.schemaVersion === 1 &&
    Array.isArray(value.items) &&
    value.items.length <= 100 &&
    value.items.every(notification) &&
    object(value.page) &&
    exact(value.page, ["limit", "hasMore", "nextCursor"]) &&
    integer(value.page.limit, 1, 100) &&
    typeof value.page.hasMore === "boolean" &&
    (value.page.nextCursor === null || text(value.page.nextCursor, 1024)) &&
    value.page.hasMore === (value.page.nextCursor !== null) &&
    object(value.permissions) &&
    exact(value.permissions, ["serverFiltered"]) &&
    value.permissions.serverFiltered === true
  );
}

export function isNotificationPreference(
  value: unknown,
): value is NotificationPreference {
  return (
    object(value) &&
    exact(value, [
      "schemaVersion",
      "emailKinds",
      "criticalAuditEmail",
      "criticalAuditMutable",
      "version",
    ]) &&
    value.schemaVersion === 1 &&
    Array.isArray(value.emailKinds) &&
    value.emailKinds.length <= 3 &&
    value.emailKinds.every((kind) =>
      EMAIL_KINDS.has(kind as OptionalEmailNotificationKind),
    ) &&
    new Set(value.emailKinds).size === value.emailKinds.length &&
    value.criticalAuditEmail === true &&
    value.criticalAuditMutable === false &&
    integer(value.version)
  );
}

function workItemDraft(value: unknown): value is MeetingWorkItemDraft {
  return (
    object(value) &&
    exact(value, [
      "itemKey",
      "kind",
      "title",
      "detail",
      "ownerUserId",
      "dueAt",
      "severity",
      "blocking",
    ]) &&
    text(value.itemKey, 64) &&
    KEY.test(value.itemKey) &&
    (value.kind === "action" || value.kind === "decision_request") &&
    text(value.title, 280) &&
    (value.detail === null || text(value.detail, 4000)) &&
    text(value.ownerUserId, 254) &&
    EMAIL.test(value.ownerUserId) &&
    dateTime(value.dueAt) &&
    ["low", "medium", "high", "critical"].includes(String(value.severity)) &&
    typeof value.blocking === "boolean"
  );
}

function draftReady(
  expectedProjectVersion: number,
  draft: MeetingMinuteDraft,
): boolean {
  const items: unknown = draft.items;
  return (
    integer(expectedProjectVersion, 1) &&
    templateRef(draft.templateRef) &&
    text(draft.title, 280) &&
    dateTime(draft.occurredAt) &&
    Array.isArray(draft.attendeeUserIds) &&
    draft.attendeeUserIds.length >= 1 &&
    draft.attendeeUserIds.length <= 100 &&
    draft.attendeeUserIds.every(
      (user) => text(user, 254) && EMAIL.test(user),
    ) &&
    new Set(draft.attendeeUserIds).size === draft.attendeeUserIds.length &&
    sections(draft.sections) &&
    Array.isArray(items) &&
    items.length <= 50 &&
    items.every(workItemDraft) &&
    new Set(items.map((item) => item.itemKey)).size === items.length
  );
}

function contextReady(context: CollaborationCommandContext): boolean {
  return (
    text(context.csrfToken, 512, 16) && IDEMPOTENCY.test(context.idempotencyKey)
  );
}

function requestNotReady(): NpiTransportError {
  return new NpiTransportError(
    "request_not_ready",
    `client-${globalThis.crypto.randomUUID()}`,
    "client",
  );
}

export class LiveCollaborationDataSource implements CollaborationDataSource {
  constructor(private readonly http = new NpiHttpClient()) {}

  async loadMeetings(
    projectId: string,
    signal: AbortSignal,
  ): Promise<MeetingMinuteCollection> {
    if (!UUID.test(projectId)) throw requestNotReady();
    return this.http.request(
      `/projects/${projectId}/meetings`,
      { signal },
      {
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: (value): value is MeetingMinuteCollection =>
          isMeetingMinuteCollection(value, projectId),
      },
    );
  }

  async createMeeting(
    projectId: string,
    expectedProjectVersion: number,
    draft: MeetingMinuteDraft,
    context: CollaborationCommandContext,
  ): Promise<MeetingMinute> {
    if (
      !UUID.test(projectId) ||
      !draftReady(expectedProjectVersion, draft) ||
      !contextReady(context)
    )
      throw requestNotReady();
    return this.http.request(
      `/projects/${projectId}/meetings`,
      {
        method: "POST",
        signal: context.signal,
        headers: { "Idempotency-Key": context.idempotencyKey },
        body: JSON.stringify({ expectedProjectVersion, ...draft }),
      },
      {
        csrfToken: context.csrfToken,
        requireIdempotencyReplay: true,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: (value): value is MeetingMinute => meeting(value, projectId),
        validateResponse: (response) => response.status === 201,
      },
    );
  }

  async loadNotifications(
    unreadOnly: boolean,
    cursor: string | undefined,
    signal: AbortSignal,
  ): Promise<InternalNotificationCollection> {
    if (cursor !== undefined && !text(cursor, 1024)) throw requestNotReady();
    return this.http.request(
      "/notifications",
      { signal },
      {
        query: {
          unreadOnly: String(unreadOnly),
          limit: "25",
          ...(cursor ? { cursor } : {}),
        },
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isInternalNotificationCollection,
      },
    );
  }

  async markNotificationRead(
    item: InternalNotification,
    context: CollaborationCommandContext,
  ): Promise<InternalNotification> {
    if (!notification(item) || item.readAt !== null || !contextReady(context))
      throw requestNotReady();
    return this.http.request(
      `/notifications/${item.globalId}:mark-read`,
      {
        method: "POST",
        signal: context.signal,
        headers: { "Idempotency-Key": context.idempotencyKey },
        body: JSON.stringify({ expectedVersion: item.version }),
      },
      {
        csrfToken: context.csrfToken,
        requireIdempotencyReplay: true,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: (value): value is InternalNotification =>
          notification(value) &&
          value.globalId === item.globalId &&
          value.readAt !== null,
      },
    );
  }

  async loadPreference(signal: AbortSignal): Promise<NotificationPreference> {
    return this.http.request(
      "/me/preferences/notifications",
      { signal },
      {
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isNotificationPreference,
      },
    );
  }

  async savePreference(
    preference: NotificationPreference,
    emailKinds: readonly OptionalEmailNotificationKind[],
    context: CollaborationCommandContext,
  ): Promise<NotificationPreference> {
    if (
      !isNotificationPreference(preference) ||
      emailKinds.length > 3 ||
      new Set(emailKinds).size !== emailKinds.length ||
      !emailKinds.every((kind) => EMAIL_KINDS.has(kind)) ||
      !contextReady(context)
    )
      throw requestNotReady();
    return this.http.request(
      "/me/preferences/notifications",
      {
        method: "PUT",
        signal: context.signal,
        headers: { "Idempotency-Key": context.idempotencyKey },
        body: JSON.stringify({
          expectedVersion: preference.version,
          emailKinds: [...emailKinds].sort(),
        }),
      },
      {
        csrfToken: context.csrfToken,
        requireIdempotencyReplay: true,
        requirePrivateNoStore: true,
        requireRequestIdEcho: true,
        requireTraceId: true,
        validate: isNotificationPreference,
      },
    );
  }
}
