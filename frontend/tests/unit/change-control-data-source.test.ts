import { describe, expect, it, vi } from "vitest";

import {
  isEngineeringChangeDetail,
  isEngineeringChangeList,
  isEngineeringChangeRevision,
  LiveChangeControlDataSource,
} from "../../src/api/change-control-data-source";
import { NpiHttpClient, NpiTransportError } from "../../src/api/http";
import {
  changeControlIds,
  engineeringChangeCommandResult,
  engineeringChangeContent,
  engineeringChangeDetail,
  engineeringChangeList,
  engineeringChangeRevision,
  engineeringChangeSummaryReceipt,
} from "../support/change-control-fixture";

describe("change control data source", () => {
  it("accepts only the exact Project-contained revision, list and detail shapes", () => {
    expect(isEngineeringChangeRevision(engineeringChangeRevision())).toBe(true);
    expect(
      isEngineeringChangeList(
        engineeringChangeList(),
        changeControlIds.project,
      ),
    ).toBe(true);
    expect(
      isEngineeringChangeDetail(
        engineeringChangeDetail(),
        changeControlIds.project,
        changeControlIds.change,
      ),
    ).toBe(true);
    expect(
      isEngineeringChangeRevision({
        ...engineeringChangeRevision(),
        leakedSecret: "not allowed",
      }),
    ).toBe(false);
    expect(
      isEngineeringChangeList(
        {
          ...engineeringChangeList(),
          projectGlobalId: "22222222-2222-4222-8222-222222222222",
        },
        changeControlIds.project,
      ),
    ).toBe(false);
    expect(
      isEngineeringChangeDetail(
        {
          ...engineeringChangeDetail(),
          events: [
            { ...engineeringChangeDetail().events[0], eventHash: "bad" },
          ],
        },
        changeControlIds.project,
        changeControlIds.change,
      ),
    ).toBe(false);
    expect(
      isEngineeringChangeDetail(
        {
          ...engineeringChangeDetail(),
          revisions: [
            {
              ...engineeringChangeDetail().revisions[0],
              globalId: "22222222-2222-4222-8222-222222222222",
            },
          ],
        },
        changeControlIds.project,
        changeControlIds.change,
      ),
    ).toBe(false);
    expect(
      isEngineeringChangeDetail(
        {
          ...engineeringChangeDetail(),
          events: [
            {
              ...engineeringChangeDetail().events[0],
              revisionGlobalId: "22222222-2222-4222-8222-222222222222",
            },
          ],
        },
        changeControlIds.project,
        changeControlIds.change,
      ),
    ).toBe(false);
  });

  it("uses only Project-first reads and exact operation-specific command bodies", async () => {
    const http = new NpiHttpClient();
    const list = engineeringChangeList();
    const detail = engineeringChangeDetail();
    const create = engineeringChangeCommandResult("engineering_change.create");
    const revise = engineeringChangeCommandResult("engineering_change.revise");
    const close = engineeringChangeCommandResult("engineering_change.close");
    const summary = engineeringChangeSummaryReceipt();
    const request = vi
      .spyOn(http, "request")
      .mockResolvedValueOnce(list)
      .mockResolvedValueOnce(detail)
      .mockResolvedValueOnce(create)
      .mockResolvedValueOnce(revise)
      .mockResolvedValueOnce(close)
      .mockResolvedValueOnce(summary);
    const source = new LiveChangeControlDataSource(http);
    const signal = new AbortController().signal;
    const context = {
      csrfToken: "c".repeat(32),
      idempotencyKey: "engineering-change-command-0001",
      signal,
    };
    const content = engineeringChangeContent();
    const current = engineeringChangeRevision();

    await source.loadChanges(changeControlIds.project, signal);
    await source.loadChange(
      changeControlIds.project,
      changeControlIds.change,
      signal,
    );
    await source.createChange(changeControlIds.project, content, context);
    await source.reviseChange(
      changeControlIds.project,
      current,
      content,
      context,
    );
    await source.closeChange(changeControlIds.project, current, context);
    await source.requestImplementationSummary(
      changeControlIds.project,
      current,
      context,
    );

    expect(request.mock.calls.map((call) => call[0])).toEqual([
      `/projects/${changeControlIds.project}/engineering-changes`,
      `/projects/${changeControlIds.project}/engineering-changes/${changeControlIds.change}`,
      `/projects/${changeControlIds.project}/engineering-changes`,
      `/projects/${changeControlIds.project}/engineering-changes/${changeControlIds.change}/revisions`,
      `/projects/${changeControlIds.project}/engineering-changes/${changeControlIds.change}:close`,
      `/projects/${changeControlIds.project}/engineering-changes/${changeControlIds.change}:request-implementation-summary`,
    ]);
    expect(request.mock.calls[2]?.[1]).toMatchObject({
      body: JSON.stringify({ content }),
      headers: { "Idempotency-Key": context.idempotencyKey },
      method: "POST",
    });
    const predecessor = {
      expectedRevision: current.revision,
      expectedRevisionGlobalId: current.globalId,
      expectedRevisionSnapshotHash: current.snapshotHash,
    };
    expect(request.mock.calls[3]?.[1]).toMatchObject({
      body: JSON.stringify({ predecessor, content }),
      method: "POST",
    });
    expect(request.mock.calls[4]?.[1]).toMatchObject({
      body: JSON.stringify({ predecessor }),
      method: "POST",
    });
    expect(request.mock.calls[5]?.[1]).toMatchObject({
      body: JSON.stringify(predecessor),
      method: "POST",
    });
  });

  it("fails before transport for invalid identity, CSRF or idempotency input", async () => {
    const http = new NpiHttpClient();
    const request = vi.spyOn(http, "request");
    const source = new LiveChangeControlDataSource(http);
    const signal = new AbortController().signal;

    await expect(
      source.loadChanges("not-a-project", signal),
    ).rejects.toBeInstanceOf(NpiTransportError);
    await expect(
      source.createChange(
        changeControlIds.project,
        engineeringChangeContent(),
        { csrfToken: "short", idempotencyKey: "bad", signal },
      ),
    ).rejects.toBeInstanceOf(NpiTransportError);
    expect(request).not.toHaveBeenCalled();
  });
});
