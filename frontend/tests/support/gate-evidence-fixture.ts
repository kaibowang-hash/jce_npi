import type { GateEvidenceViewModel } from "../../src/domain/view-models";

export function gateEvidenceFixture(
  overrides: Partial<GateEvidenceViewModel> = {},
): GateEvidenceViewModel {
  const fixture: GateEvidenceViewModel = {
    project: {
      globalId: "11111111-1111-4111-8111-111111111111",
      businessCode: "SYN-PROJECT-001",
      title: "Synthetic project cockpit",
    },
    gate: {
      globalId: "44444444-4444-4444-8444-444444444444",
      key: "G1",
      title: "Synthetic initiation evidence",
      state: "not_started",
      version: 2,
      dueDate: "2026-08-15",
      templateRef: {
        globalId: "66666666-6666-4666-8666-666666666666",
        version: 1,
        snapshotHash: "1".repeat(64),
      },
      requirementSnapshotHash: "2".repeat(64),
      frozenAt: "2026-07-23T10:15:00Z",
      frozenBy: "Administrator",
    },
    requirements: [
      {
        globalId: "12121212-1212-4212-8212-121212121212",
        key: "DESIGN_BASELINE",
        title: "Synthetic design baseline",
        classification: "required",
        priority: "P0",
        owner: {
          memberId: "77777777-7777-4777-8777-777777777777",
          userId: "engineering.lead@example.invalid",
          displayName: "Synthetic Engineering Lead",
        },
        reviewers: [
          {
            memberId: "88888888-8888-4888-8888-888888888888",
            userId: "quality.lead@example.invalid",
            displayName: "Synthetic Quality Lead",
          },
        ],
        dueDate: "2026-08-10",
        allowedEvidenceKinds: ["wbs_item"],
        evidenceState: "attached",
        evidence: [
          {
            globalId: "99999999-9999-4999-8999-999999999999",
            kind: "wbs_item",
            sourceObjectType: "wbs_item",
            sourceGlobalId: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            revision: 3,
            objectHash: "3".repeat(64),
            createdAt: "2026-07-23T10:20:00Z",
            createdBy: "engineering.lead@example.invalid",
          },
        ],
      },
      {
        globalId: "23232323-2323-4232-8232-232323232323",
        key: "DIMENSIONAL_REPORT",
        title: "Synthetic dimensional report",
        classification: "required",
        priority: "P0",
        owner: {
          memberId: "88888888-8888-4888-8888-888888888888",
          userId: "quality.lead@example.invalid",
          displayName: "Synthetic Quality Lead",
        },
        reviewers: [
          {
            memberId: "77777777-7777-4777-8777-777777777777",
            userId: "engineering.lead@example.invalid",
            displayName: "Synthetic Engineering Lead",
          },
        ],
        dueDate: "2026-08-12",
        allowedEvidenceKinds: ["file_revision"],
        evidenceState: "scan_pending",
        evidence: [
          {
            globalId: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            kind: "file_revision",
            sourceObjectType: "file_revision",
            sourceGlobalId: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            revision: 1,
            objectHash: "4".repeat(64),
            createdAt: "2026-07-23T10:25:00Z",
            createdBy: "quality.lead@example.invalid",
            file: {
              fileName: "SYN-DIMENSIONAL-REPORT.pdf",
              mimeType: "application/pdf",
              sizeBytes: 24832,
              scanState: "pending",
            },
          },
        ],
      },
      {
        globalId: "34343434-3434-4343-8343-343434343434",
        key: "CUSTOMER_CONFIRMATION",
        title: "Synthetic customer confirmation",
        classification: "optional",
        priority: "P1",
        owner: {
          memberId: "77777777-7777-4777-8777-777777777777",
          userId: "engineering.lead@example.invalid",
          displayName: "Synthetic Engineering Lead",
        },
        reviewers: [
          {
            memberId: "88888888-8888-4888-8888-888888888888",
            userId: "quality.lead@example.invalid",
            displayName: "Synthetic Quality Lead",
          },
        ],
        dueDate: "2026-08-15",
        allowedEvidenceKinds: ["file_revision"],
        evidenceState: "missing",
        evidence: [],
      },
    ],
    summary: {
      requiredCount: 2,
      missingRequiredCount: 0,
      unsafeScanCount: 1,
      evidenceCount: 2,
    },
    permissions: {
      canView: true,
      canAttachEvidence: false,
      canAdminister: false,
    },
  };
  return { ...fixture, ...overrides };
}
