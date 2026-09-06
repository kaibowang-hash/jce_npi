import type {
  CollaborationCommandContext,
  CollaborationDataSource,
  InternalNotification,
  InternalNotificationCollection,
  MeetingMinute,
  MeetingMinuteCollection,
  MeetingMinuteDraft,
  NotificationPreference,
  OptionalEmailNotificationKind,
} from "../../src/api/collaboration-data-source";
import { reportingProjectId } from "./reporting-fixture";

export const syntheticNotificationId = "33333333-3333-4333-8333-333333333333";

export function notificationFixture(
  overrides: Partial<InternalNotification> = {},
): InternalNotification {
  return {
    schemaVersion: 1,
    globalId: syntheticNotificationId,
    projectId: reportingProjectId,
    source: {
      type: "domain_work_item",
      globalId: "44444444-4444-4444-8444-444444444444",
      version: 2,
    },
    kind: "due_reminder",
    criticalAudit: false,
    titleSource: "Work item due soon",
    messageParameters: { dueAt: "2026-09-02T08:00:00Z" },
    targetRoute: `/projects/${reportingProjectId}/work`,
    sourceDueAt: "2026-09-02T08:00:00Z",
    emailDeliveryState: "queued",
    failureCode: null,
    readAt: null,
    createdAt: "2026-09-01T08:00:00Z",
    version: 1,
    ...overrides,
  };
}

export function meetingCollectionFixture(): MeetingMinuteCollection {
  return {
    schemaVersion: 1,
    projectId: reportingProjectId,
    projectVersion: 3,
    items: [],
    permissions: {
      canView: true,
      canContribute: true,
      canAdminister: true,
    },
  };
}

export function notificationPreferenceFixture(): NotificationPreference {
  return {
    schemaVersion: 1,
    emailKinds: ["due_reminder"],
    criticalAuditEmail: true,
    criticalAuditMutable: false,
    version: 1,
  };
}

export class SyntheticCollaborationDataSource implements CollaborationDataSource {
  loadMeetings(projectId: string): Promise<MeetingMinuteCollection> {
    return Promise.resolve({ ...meetingCollectionFixture(), projectId });
  }

  createMeeting(
    projectId: string,
    expectedProjectVersion: number,
    draft: MeetingMinuteDraft,
    context: CollaborationCommandContext,
  ): Promise<MeetingMinute> {
    void context;
    return Promise.resolve({
      schemaVersion: 1,
      globalId: "55555555-5555-4555-8555-555555555555",
      projectId,
      projectVersion: expectedProjectVersion + 1,
      templateRef: draft.templateRef,
      title: draft.title,
      occurredAt: draft.occurredAt,
      attendeeUserIds: draft.attendeeUserIds,
      sections: draft.sections,
      linkedItems: draft.items.map((item, index) => {
        const workItemId = `66666666-6666-4666-8666-66666666666${String(index)}`;
        return {
          itemKey: item.itemKey,
          kind: item.kind,
          workItemId,
          title: item.title,
          ownerUserId: item.ownerUserId,
          dueAt: item.dueAt,
          targetRoute: `/projects/${projectId}/work?workItemId=${workItemId}`,
        };
      }),
      contentHash: "a".repeat(64),
      createdBy: "project.admin@example.invalid",
      createdAt: "2026-09-01T08:00:00Z",
      version: 1,
    });
  }

  loadNotifications(): Promise<InternalNotificationCollection> {
    return Promise.resolve({
      schemaVersion: 1,
      items: [notificationFixture()],
      page: { limit: 25, hasMore: false, nextCursor: null },
      permissions: { serverFiltered: true },
    });
  }

  markNotificationRead(
    notification: InternalNotification,
  ): Promise<InternalNotification> {
    return Promise.resolve({
      ...notification,
      readAt: "2026-09-01T09:00:00Z",
      version: notification.version + 1,
    });
  }

  loadPreference(): Promise<NotificationPreference> {
    return Promise.resolve(notificationPreferenceFixture());
  }

  savePreference(
    preference: NotificationPreference,
    emailKinds: readonly OptionalEmailNotificationKind[],
  ): Promise<NotificationPreference> {
    return Promise.resolve({
      ...preference,
      emailKinds,
      version: preference.version + 1,
    });
  }
}
