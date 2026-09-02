import { describe, expect, it, vi } from "vitest";

import {
  isInternalNotificationCollection,
  isMeetingMinuteCollection,
  isNotificationPreference,
  LiveCollaborationDataSource,
} from "../../src/api/collaboration-data-source";
import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import {
  meetingCollectionFixture,
  notificationFixture,
  notificationPreferenceFixture,
  SyntheticCollaborationDataSource,
} from "../support/collaboration-fixture";
import { reportingProjectId as projectId } from "../support/reporting-fixture";

describe("collaboration data source", () => {
  it("uses operation-specific meeting and notification paths", async () => {
    const fixtureSource = new SyntheticCollaborationDataSource();
    const collection = meetingCollectionFixture();
    const preference = notificationPreferenceFixture();
    const draft = {
      templateRef: {
        globalId: "00000000-0000-4000-8000-000000000902",
        version: 1 as const,
        snapshotHash:
          "6e8cdc80e514c8cd594d780bb8251a35a0b415e649a7ac529b77b1b9917a6a4c",
      },
      title: "Synthetic review",
      occurredAt: "2026-09-01T08:00:00Z",
      attendeeUserIds: ["project.admin@example.invalid"],
      sections: {
        agenda: "Agenda",
        discussion: "Discussion",
        decisions: "Decision",
      },
      items: [],
    };
    const created = await fixtureSource.createMeeting(projectId, 3, draft, {
      csrfToken: "c".repeat(32),
      idempotencyKey: "p902-meeting-0001",
      signal: new AbortController().signal,
    });
    const read = notificationFixture({
      readAt: "2026-09-01T09:00:00Z",
      version: 2,
    });
    const http = new NpiHttpClient();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(collection)
      .mockResolvedValueOnce(created)
      .mockResolvedValueOnce({
        schemaVersion: 1,
        items: [notificationFixture()],
        page: { limit: 25, hasMore: false, nextCursor: null },
        permissions: { serverFiltered: true },
      })
      .mockResolvedValueOnce(read)
      .mockResolvedValueOnce(preference)
      .mockResolvedValueOnce({
        ...preference,
        emailKinds: ["gate_attention"],
        version: 2,
      });
    const source = new LiveCollaborationDataSource(http);
    const signal = new AbortController().signal;
    const context = {
      csrfToken: "c".repeat(32),
      idempotencyKey: "p902-command-0001",
      signal,
    };

    await source.loadMeetings(projectId, signal);
    await source.createMeeting(projectId, 3, draft, context);
    await source.loadNotifications(false, undefined, signal);
    await source.markNotificationRead(notificationFixture(), context);
    await source.loadPreference(signal);
    await source.savePreference(preference, ["gate_attention"], context);

    expect(request.mock.calls.map((call) => call[0])).toEqual([
      `/projects/${projectId}/meetings`,
      `/projects/${projectId}/meetings`,
      "/notifications",
      "/notifications/33333333-3333-4333-8333-333333333333:mark-read",
      "/me/preferences/notifications",
      "/me/preferences/notifications",
    ]);
    expect(request.mock.calls[1]?.[1]).toMatchObject({
      method: "POST",
      headers: { "Idempotency-Key": "p902-command-0001" },
    });
  });

  it("rejects extra fields and inconsistent protected notification truth", () => {
    expect(
      isMeetingMinuteCollection(meetingCollectionFixture(), projectId),
    ).toBe(true);
    expect(
      isMeetingMinuteCollection(
        { ...meetingCollectionFixture(), rawScript: "secret" },
        projectId,
      ),
    ).toBe(false);
    const collection = {
      schemaVersion: 1,
      items: [notificationFixture()],
      page: { limit: 25, hasMore: false, nextCursor: null },
      permissions: { serverFiltered: true },
    };
    expect(isInternalNotificationCollection(collection)).toBe(true);
    expect(
      isInternalNotificationCollection({
        ...collection,
        items: [notificationFixture({ criticalAudit: true })],
      }),
    ).toBe(false);
    expect(
      isInternalNotificationCollection({
        ...collection,
        items: [
          notificationFixture({
            targetRoute: `/projects/${projectId}-suffix`,
          }),
        ],
      }),
    ).toBe(false);
    expect(isNotificationPreference(notificationPreferenceFixture())).toBe(
      true,
    );
    expect(
      isNotificationPreference({
        ...notificationPreferenceFixture(),
        criticalAuditMutable: true,
      }),
    ).toBe(false);
  });

  it("rejects unsafe command inputs before transport", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const source = new LiveCollaborationDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.loadMeetings("not-a-project", signal),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.markNotificationRead(
        notificationFixture({ readAt: "2026-09-01T09:00:00Z" }),
        {
          csrfToken: "c".repeat(32),
          idempotencyKey: "p902-command-0002",
          signal,
        },
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(request).not.toHaveBeenCalled();
  });
});
