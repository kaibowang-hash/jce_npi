import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import type {
  PartControlledSpecificationContextViewModel,
  ToolingCockpitViewModel,
  ToolingEngineeringControlsViewModel,
  ToolAssetRequestCollectionViewModel,
  ToolAssetRequestViewModel,
  ToolingAcceptanceAssetContextViewModel,
  ToolingAcceptanceEvidenceRevisionViewModel,
  ToolingMeasurementViewModel,
  ToolingManufacturingMilestoneObservationViewModel,
  ToolingManufacturingPlanCollectionViewModel,
  ToolingManufacturingPlanRevisionViewModel,
  ToolingProcessChainCollectionViewModel,
  ToolingReleasedDocumentEvidenceViewModel,
  ToolingProcessChainRevisionViewModel,
  ToolingRevisionCollectionViewModel,
  ToolingRevisionDetailViewModel,
  ToolingRevisionViewModel,
  ToolingSetCollectionViewModel,
  ToolingSetDetailViewModel,
} from "../../src/api/tooling-data-source";
import {
  acceptanceContext as baseAcceptanceContext,
  acceptanceRevision as baseAcceptanceRevision,
  assetRequest as baseAssetRequest,
  toolAssetProjectionCollection,
} from "../support/tooling-acceptance-fixture";
import {
  toolingListPage,
  toolingListPreference,
} from "../support/tooling-list-fixture";
import {
  toolAssetExecutionCollection,
  toolAssetExecutionContext,
  toolAssetExecutionDetail,
  toolAssetExecutionRequestId,
} from "../support/tool-asset-execution-fixture";
import {
  effectiveViewport,
  expectIndustrialComputedStyles,
  expectNoDocumentOverflow,
  expectNoMixedLanguage,
  type TestLocale,
} from "./support";

const projectId = "11111111-1111-4111-8111-111111111111";
const masterId = "22222222-2222-4222-8222-222222222222";
const toolingRevisionId = "33333333-3333-4333-8333-333333333333";
const applicabilityId = "44444444-4444-4444-8444-444444444444";
const cavityId = "55555555-5555-4555-8555-555555555555";
const partId = "66666666-6666-4666-8666-666666666666";
const partRevisionId = "77777777-7777-4777-8777-777777777777";
const requirementId = "88888888-8888-4888-8888-888888888888";
const controlledSpecificationId = "99999999-9999-4999-8999-999999999999";
const specificationItemId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const processChainId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const processChainRevisionId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const firstStepId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const secondStepId = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const setId = "ffffffff-ffff-4fff-8fff-ffffffffffff";
const bindingId = "12345678-1234-4234-8234-123456789abc";
const manufacturingPlanId = "13572468-1357-4357-8357-246813572468";
const manufacturingPlanRevisionId = "24681357-2468-4468-8468-135724681357";
const manufacturingMemberId = "35792468-3579-4579-8579-246813579246";
const manufacturingMilestoneId = "46813579-4681-4681-8681-357924683579";
const manufacturingObservationId = "57924681-5792-4792-8792-468135794681";
const designDocumentRevisionId = "68135792-6813-4813-8813-579246816813";
const designLifecycleId = "79246813-7924-4924-8924-681357927924";
const designReleaseEventId = "81357924-8135-4135-8135-792468138135";
const defectId = "90111111-1111-4111-8111-111111111111";
const defectRevisionId = "90222222-2222-4222-8222-222222222222";
const defectActionId = "90333333-3333-4333-8333-333333333333";
const processProfileId = "90444444-4444-4444-8444-444444444444";
const processProfileRevisionId = "90555555-5555-4555-8555-555555555555";
const processMetricId = "90666666-6666-4666-8666-666666666666";
const capacityScenarioId = "90777777-7777-4777-8777-777777777777";
const capacityScenarioRevisionId = "90888888-8888-4888-8888-888888888888";
const capacityLineId = "90999999-9999-4999-8999-999999999999";
const acceptanceId = "91011111-1111-4111-8111-111111111111";
const acceptanceRevisionId = "92022222-2222-4222-8222-222222222222";
const acceptanceSuccessorRevisionId = "92555555-5555-4555-8555-555555555555";
const assetRequestId = "93033333-3333-4333-8333-333333333333";
const csrfToken = "p6-03-tooling-revision-browser-csrf";
const requestIdPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const sessionEndpoint = /\/api\/npi\/v1\/session\/bootstrap(?:\?.*)?$/u;
const projectEndpoint = /\/api\/npi\/v1\/projects\/[^/?]+\/.+/u;

interface ObservedRequest {
  idempotencyKey: string | undefined;
  method: string;
  path: string;
  payload: unknown;
}

const unavailable = {
  combinedTrial: {
    reasonCode: "combined_trial_not_delivered" as const,
    state: "unavailable" as const,
  },
  erpLocationAndAsset: {
    reasonCode: "erp_projection_unavailable" as const,
    state: "unavailable" as const,
  },
  lifecycle: {
    reasonCode: "lifecycle_policy_unavailable" as const,
    state: "unavailable" as const,
  },
  supplier: {
    reasonCode: "formal_supplier_unavailable" as const,
    state: "unavailable" as const,
  },
};

const permissions = {
  bindSetSource: true,
  createPartSpecification: true,
  createProcessChain: true,
  createRevision: true,
  transitionLifecycle: false as const,
  view: true,
};

function measurement(value: string, unit: string): ToolingMeasurementViewModel {
  return { source: "Engineering", unit, value };
}

function revision(): ToolingRevisionViewModel {
  return {
    cavities: [
      {
        cavityIdentifier: "C01",
        globalId: cavityId,
        partRevisionGlobalId: partRevisionId,
        structuralState: "enabled",
        toolingApplicabilityGlobalId: applicabilityId,
      },
    ],
    designDocumentRevisions: [],
    externalIdentities: [],
    globalId: toolingRevisionId,
    inserts: [],
    predecessorGlobalId: null,
    reason: "Controlled production release",
    revisionLabel: "R1",
    revisionNumber: 1,
    snapshotHash: "a".repeat(64),
    specification: {
      cavityCount: 1,
      clampTonnage: measurement("180", "t"),
      coreMaterial: "H13",
      customerStandard: "STD-001",
      deliveryDocuments: ["Inspection report"],
      hardness: measurement("48", "HRC"),
      height: measurement("320", "mm"),
      hotRunner: "Valve gate",
      injectionCapacity: measurement("450", "g"),
      interfaceRequirement: "EUROMAP",
      length: measurement("600", "mm"),
      machineType: "Injection molding",
      moldBaseMaterial: "P20",
      spareParts: ["Seal kit"],
      surfaceTreatment: "Nitrided",
      targetCycle: measurement("35", "s"),
      targetLife: measurement("500000", "cycles"),
      tieBarSpacingX: measurement("700", "mm"),
      tieBarSpacingY: measurement("650", "mm"),
      toolingType: "Two-plate mold",
      warranty: "12 months",
      weight: measurement("820", "kg"),
      width: measurement("520", "mm"),
    },
    toolingMasterGlobalId: masterId,
  };
}

function revisionCollection(): ToolingRevisionCollectionViewModel {
  return {
    ...unavailable,
    items: [revision()],
    permissions,
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
  };
}

function revisionDetail(): ToolingRevisionDetailViewModel {
  return {
    ...unavailable,
    permissions,
    projectGlobalId: projectId,
    revision: revision(),
  };
}

function partContext(
  recorded = true,
): PartControlledSpecificationContextViewModel {
  return {
    automaticImpact: {
      reasonCode: "automatic_impact_not_delivered",
      state: "unavailable",
    },
    controlledSpecification: recorded
      ? {
          externalIdentities: [],
          globalId: controlledSpecificationId,
          items: [
            {
              effectiveFrom: "2026-08-08",
              effectiveTo: null,
              globalId: specificationItemId,
              kind: "material_family",
              normalizedValue: "PA66",
              rawValue: "PA66-GF30",
              sourceObjectId: "PART-SPEC-001",
              sourceSystem: "NPI_ONE",
              unit: null,
            },
          ],
          partGlobalId: partId,
          partRevisionGlobalId: partRevisionId,
          partRevisionSnapshotHash: "b".repeat(64),
          snapshotHash: "c".repeat(64),
        }
      : {
          reasonCode: "controlled_part_specification_not_recorded",
          state: "unavailable",
        },
    partGlobalId: partId,
    partRevision: {
      globalId: partRevisionId,
      partGlobalId: partId,
      revisionLabel: "A",
      revisionNumber: 1,
      snapshotHash: "b".repeat(64),
    },
    permissions,
    projectGlobalId: projectId,
  };
}

function processChain(): ToolingProcessChainRevisionViewModel {
  return {
    chainVersion: 1,
    globalId: processChainRevisionId,
    predecessorGlobalId: null,
    processChainGlobalId: processChainId,
    reason: "Primary molding and overmold sequence",
    snapshotHash: "d".repeat(64),
    steps: [
      {
        clampTonnage: measurement("180", "t"),
        globalId: firstStepId,
        inputPartRevisionGlobalIds: [partRevisionId],
        machineType: "Injection molding",
        outputPartRevisionGlobalId: partRevisionId,
        parentStepGlobalId: null,
        processKind: "primary_molding",
        stepOrder: 1,
        toolingRevisionGlobalId: toolingRevisionId,
        toolingRevisionSnapshotHash: "a".repeat(64),
      },
      {
        clampTonnage: measurement("120", "t"),
        globalId: secondStepId,
        inputPartRevisionGlobalIds: [partRevisionId],
        machineType: "Overmolding",
        outputPartRevisionGlobalId: partRevisionId,
        parentStepGlobalId: firstStepId,
        processKind: "overmold",
        stepOrder: 2,
        toolingRevisionGlobalId: toolingRevisionId,
        toolingRevisionSnapshotHash: "a".repeat(64),
      },
    ],
  };
}

function chainCollection(): ToolingProcessChainCollectionViewModel {
  return {
    combinedTrial: unavailable.combinedTrial,
    items: [processChain()],
    permissions,
    projectGlobalId: projectId,
  };
}

function cockpit(): ToolingCockpitViewModel {
  const source = {
    editableIn: "NPI_ONE" as const,
    sourceSystem: "NPI_ONE" as const,
    syncState: "local" as const,
  };
  return {
    applicability: [
      {
        effectiveFrom: "2026-08-08",
        effectiveTo: null,
        globalId: applicabilityId,
        model: null,
        part: {
          globalId: partRevisionId,
          partGlobalId: partId,
          revisionLabel: "A",
          revisionNumber: 1,
          snapshotHash: "b".repeat(64),
        },
        predecessorGlobalId: null,
        product: null,
        projectGlobalId: projectId,
        relationshipGlobalId: "87654321-4321-4321-8321-cba987654321",
        relationshipKeyHash: "e".repeat(64),
        snapshotHash: "f".repeat(64),
        toolingMasterGlobalId: masterId,
        version: 1,
      },
    ],
    downstream: {
      erp: { reasonCode: "erp_projection_unavailable", state: "unavailable" },
      lifecycle: {
        reasonCode: "lifecycle_policy_unavailable",
        state: "unavailable",
      },
      physicalSet: {
        reasonCode: "physical_set_not_delivered",
        state: "unavailable",
      },
      revision: {
        reasonCode: "tooling_revision_available",
        revisionCount: 1,
        state: "available",
      },
      trial: { reasonCode: "trial_not_delivered", state: "unavailable" },
    },
    masters: [
      {
        globalId: masterId,
        originatingProjectGlobalId: projectId,
        snapshotHash: "1".repeat(64),
        source,
        title: "Synthetic revision-controlled mold",
      },
    ],
    parts: [
      {
        currentRevision: {
          globalId: partRevisionId,
          partGlobalId: partId,
          revisionLabel: "A",
          revisionNumber: 1,
          snapshotHash: "b".repeat(64),
        },
        globalId: partId,
        source,
        title: "Synthetic valve body",
        version: 1,
      },
    ],
    permissions: {
      createApplicability: false,
      createMaster: false,
      createPart: false,
      createRequirement: false,
      transitionLifecycle: false,
      view: true,
    },
    project: {
      businessCode: "SYN-PROJECT-003",
      globalId: projectId,
      title: "Synthetic Revision Project",
    },
    requirements: [
      {
        globalId: requirementId,
        kind: "customer_owned_intake",
        projectGlobalId: projectId,
        reason: "Controlled physical Set",
        snapshotHash: "2".repeat(64),
        targetDate: null,
        targetPartRevisionGlobalId: partRevisionId,
        title: "Controlled Set requirement",
      },
    ],
  };
}

function setCollection(): ToolingSetCollectionViewModel {
  return {
    items: [
      {
        custodyResponsibility: "Tool room custody",
        customer: null,
        erpLocationAndAsset: unavailable.erpLocationAndAsset,
        globalId: setId,
        lifecycle: unavailable.lifecycle,
        physicalSerial: "SET-REV-001",
        projectGlobalId: projectId,
        repairAuthorizationReference: "AUTH-REV-001",
        requirementKind: "customer_owned_intake",
        returnConditions: "Return after approved request",
        snapshotHash: "3".repeat(64),
        sourceRevision: {
          reasonCode: "tooling_revision_not_delivered",
          state: "unavailable",
        },
        supplier: unavailable.supplier,
        toolingMasterGlobalId: masterId,
        toolingRequirementGlobalId: requirementId,
      },
    ],
    permissions: {
      attachEvidence: false,
      createIntake: false,
      createSet: false,
      transitionLifecycle: false,
      view: true,
    },
    toolingMasterGlobalId: masterId,
  };
}

function setDetail(bound = false): ToolingSetDetailViewModel {
  const toolingSet = setCollection().items[0];
  if (!toolingSet) throw new Error("The Set fixture is required.");
  return {
    evidence: [],
    intakes: [],
    permissions: setCollection().permissions,
    toolingSet: bound
      ? {
          ...toolingSet,
          sourceRevision: {
            globalId: bindingId,
            reason: "Approved immutable source",
            snapshotHash: "4".repeat(64),
            toolingMasterGlobalId: masterId,
            toolingRevisionGlobalId: toolingRevisionId,
            toolingRevisionSnapshotHash: revision().snapshotHash,
            toolingSetGlobalId: setId,
            toolingSetSnapshotHash: toolingSet.snapshotHash,
          },
        }
      : toolingSet,
  };
}

function acceptanceEvidence(
  successor = false,
): ToolingAcceptanceEvidenceRevisionViewModel {
  const base = baseAcceptanceRevision();
  return {
    ...base,
    acceptanceGlobalId: acceptanceId,
    acceptanceVersion: successor ? 2 : 1,
    globalId: successor ? acceptanceSuccessorRevisionId : acceptanceRevisionId,
    predecessorGlobalId: successor ? acceptanceRevisionId : null,
    predecessorSnapshotHash: successor ? base.snapshotHash : null,
    projectGlobalId: projectId,
    setRevisionBindingGlobalId: bindingId,
    setRevisionBindingSnapshotHash: "4".repeat(64),
    snapshotHash: successor ? "7".repeat(64) : "6".repeat(64),
    toolingMasterGlobalId: masterId,
    toolingMasterSnapshotHash: "1".repeat(64),
    toolingRequirementKind: "customer_owned_intake",
    toolingRevisionGlobalId: toolingRevisionId,
    toolingRevisionNumber: revision().revisionNumber,
    toolingRevisionSnapshotHash: revision().snapshotHash,
    toolingSetGlobalId: setId,
    toolingSetSnapshotHash: "3".repeat(64),
  };
}

function acceptanceAssetContext(): ToolingAcceptanceAssetContextViewModel {
  return {
    ...baseAcceptanceContext(),
    acceptanceRevisions: [acceptanceEvidence()],
    assetRequests: [],
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
  };
}

function toolAssetRequest(): ToolAssetRequestViewModel {
  const base = baseAssetRequest();
  const acceptance = acceptanceEvidence();
  return {
    ...base,
    globalId: assetRequestId,
    requestId: assetRequestId,
    requestInput: {
      ...base.requestInput,
      acceptanceRevisionGlobalId: acceptance.globalId,
      acceptanceSnapshotHash: acceptance.snapshotHash,
      acceptanceVersion: acceptance.acceptanceVersion,
      projectGlobalId: projectId,
      setRevisionBindingGlobalId: bindingId,
      setRevisionBindingSnapshotHash: "4".repeat(64),
      toolingMasterGlobalId: masterId,
      toolingMasterSnapshotHash: "1".repeat(64),
      toolingMasterTitle: "Synthetic revision-controlled mold",
      toolingRequirementKind: "customer_owned_intake",
      toolingRevisionGlobalId: toolingRevisionId,
      toolingRevisionLabel: revision().revisionLabel,
      toolingRevisionNumber: revision().revisionNumber,
      toolingRevisionSnapshotHash: revision().snapshotHash,
      toolingSetGlobalId: setId,
      toolingSetPhysicalSerial: "SET-REV-001",
      toolingSetSnapshotHash: "3".repeat(64),
    },
  };
}

function toolAssetRequestCollection(): ToolAssetRequestCollectionViewModel {
  return {
    items: [toolAssetRequest()],
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
  };
}

function releasedDesignEvidence(): ToolingReleasedDocumentEvidenceViewModel {
  return {
    lifecycleGlobalId: designLifecycleId,
    lifecycleVersion: 2,
    releaseEventGlobalId: designReleaseEventId,
    releaseEventHash: "5".repeat(64),
    releaseSnapshotHash: "6".repeat(64),
    revisionGlobalId: designDocumentRevisionId,
    revisionSnapshotHash: "7".repeat(64),
  };
}

function manufacturingPlan(): ToolingManufacturingPlanRevisionViewModel {
  return {
    budget: { amount: "125000.00", currency: "CNY" },
    designReleaseEvidence: [releasedDesignEvidence()],
    engineeringEstimate: { amount: "120000", currency: "CNY" },
    evidence: [{ document: releasedDesignEvidence(), role: "dfm" }],
    globalId: manufacturingPlanRevisionId,
    milestones: [
      {
        category: "machining",
        globalId: manufacturingMilestoneId,
        plannedFinish: "2026-09-20",
        plannedStart: "2026-09-01",
        predecessorGlobalIds: [],
        responsibleMember: null,
        responsibilityKind: "supplier",
        sequence: 1,
        snapshotHash: "8".repeat(64),
      },
    ],
    planGlobalId: manufacturingPlanId,
    planVersion: 1,
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    reason: "Initial controlled manufacturing plan",
    responsibleMember: {
      globalId: manufacturingMemberId,
      optimisticVersion: 3,
      userId: "tooling.engineer@example.invalid",
    },
    snapshotHash: "9".repeat(64),
    sourcingStrategy: "hybrid",
    toolingMasterGlobalId: masterId,
    toolingRevisionGlobalId: toolingRevisionId,
    toolingRevisionSnapshotHash: revision().snapshotHash,
  };
}

function manufacturingObservation(): ToolingManufacturingMilestoneObservationViewModel {
  return {
    actualFinish: null,
    actualStart: "2026-09-02",
    evidence: [],
    globalId: manufacturingObservationId,
    milestoneGlobalId: manufacturingMilestoneId,
    milestoneSnapshotHash: "8".repeat(64),
    note: "Machining fixture completed",
    observationVersion: 1,
    planRevisionGlobalId: manufacturingPlanRevisionId,
    planRevisionSnapshotHash: "9".repeat(64),
    predecessorGlobalId: null,
    predecessorSnapshotHash: null,
    progressPercentage: 40,
    reportedByMember: {
      globalId: manufacturingMemberId,
      optimisticVersion: 3,
      userId: "tooling.engineer@example.invalid",
    },
    risk: "Cooling insert lead time",
    snapshotHash: "a".repeat(64),
  };
}

function manufacturingCollection(): ToolingManufacturingPlanCollectionViewModel {
  return {
    erpProjection: {
      editableIn: "ERPNEXT",
      reasonCode: "erp_projection_unavailable",
      sourceSystem: "ERPNEXT",
      state: "unavailable",
    },
    items: [
      {
        designReleaseEvidence: {
          items: [releasedDesignEvidence()],
          reasonCode: null,
          state: "satisfied",
        },
        observations: [manufacturingObservation()],
        plan: manufacturingPlan(),
      },
    ],
    manufacturingAuthorization: {
      reasonCode: "tooling_lifecycle_policy_unavailable",
      state: "unavailable",
    },
    permissions: {
      createPlan: true,
      editErpProjection: false,
      observeMilestone: true,
      transitionLifecycle: false,
      view: true,
    },
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
  };
}

function manufacturingDetail() {
  const value = manufacturingCollection();
  const item = value.items[0];
  if (!item) throw new Error("The manufacturing fixture is required.");
  return {
    erpProjection: value.erpProjection,
    item,
    manufacturingAuthorization: value.manufacturingAuthorization,
    permissions: value.permissions,
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
  };
}

function engineeringControls(): ToolingEngineeringControlsViewModel {
  return {
    capacityScenarioRevisions: [
      {
        createdAt: "2026-08-08T12:10:00Z",
        createdByUserId: "tooling.engineer@example.invalid",
        effectiveFrom: "2026-08-08",
        formulaVersion: "capacity.v1",
        globalId: capacityScenarioRevisionId,
        lines: [
          {
            applicabilityGlobalId: applicabilityId,
            applicabilitySnapshotHash: "f".repeat(64),
            availableHoursPerDay: "20",
            cavityCount: 1,
            cavityProvenance: {
              globalId: toolingRevisionId,
              kind: "tooling_revision",
              snapshotHash: revision().snapshotHash,
            },
            cycleProvenance: {
              globalId: processProfileRevisionId,
              kind: "customer_standard",
              snapshotHash: "c".repeat(64),
            },
            cycleSeconds: "35",
            effectiveSetCount: 1,
            globalId: capacityLineId,
            oeeRatio: "0.8",
            partRevisionGlobalId: partRevisionId,
            partRevisionSnapshotHash: "b".repeat(64),
            selectedToolingSetGlobalIds: [setId],
            setProvenance: {
              globalId: setId,
              kind: "tooling_set_selection",
              snapshotHash: "3".repeat(64),
            },
            usagePerAssembly: "1",
            usageProvenance: {
              globalId: applicabilityId,
              kind: "tooling_applicability",
              snapshotHash: "f".repeat(64),
            },
            workingDaysPerMonth: 26,
            yieldRatio: "0.95",
          },
        ],
        predecessorGlobalId: null,
        predecessorSnapshotHash: null,
        projectGlobalId: projectId,
        reason: "Initial controlled capacity scenario",
        requestId: capacityScenarioRevisionId,
        result: {
          bottleneckLineGlobalIds: [capacityLineId],
          formulaVersion: "capacity.v1",
          gap: "100.000000",
          lineResults: [
            {
              assemblyUnitsPerDay: "1954.285714",
              assemblyUnitsPerMonth: "50811.428571",
              globalId: capacityLineId,
              partsPerDay: "1954.285714",
              partsPerMonth: "50811.428571",
            },
          ],
          roundingRule: "decimal-6-half-even",
          scenarioAssemblyUnitsPerMonth: "50811.428571",
        },
        roundingRule: "decimal-6-half-even",
        scenarioGlobalId: capacityScenarioId,
        scenarioVersion: 1,
        schemaVersion: 1,
        snapshotHash: "8".repeat(64),
        targetMonthlyAssemblyUnits: "50911.428571",
        tenantId: "tenant.synthetic",
        title: "Nominal monthly capacity",
        toolingMasterGlobalId: masterId,
        traceId: "trace-p6-05-engineering-controls",
        versionKeyHash: "7".repeat(64),
      },
    ],
    defectRevisions: [
      {
        actions: [
          {
            actionType: "corrective",
            detail: "Correct ejector alignment",
            dueDate: "2026-08-20",
            evidence: [],
            globalId: defectActionId,
            responsibleMember: {
              globalId: manufacturingMemberId,
              optimisticVersion: 3,
              userId: "tooling.engineer@example.invalid",
            },
            state: "completed",
          },
        ],
        blocking: true,
        businessCode: "DEF-001",
        categoryKey: "fit_and_function",
        cavityGlobalId: cavityId,
        cavityIdentifier: "C01",
        createdAt: "2026-08-08T12:00:00Z",
        createdByUserId: "tooling.engineer@example.invalid",
        defectGlobalId: defectId,
        defectVersion: 1,
        description: "Ejector alignment is outside specification.",
        detectionContext: {
          globalId: toolingRevisionId,
          kind: "tooling_revision",
          snapshotHash: revision().snapshotHash,
        },
        evidence: [],
        globalId: defectRevisionId,
        predecessorGlobalId: null,
        predecessorSnapshotHash: null,
        projectGlobalId: projectId,
        reason: "Initial controlled finding",
        requestId: defectRevisionId,
        responsibleMember: {
          globalId: manufacturingMemberId,
          optimisticVersion: 3,
          userId: "tooling.engineer@example.invalid",
        },
        rootCause: "Machining alignment drift",
        rootCauseState: "recorded",
        schemaVersion: 1,
        severity: "high",
        snapshotHash: "2".repeat(64),
        state: "ready_for_verification",
        targetRoundLabel: "T1 intention",
        tenantId: "tenant.synthetic",
        title: "Ejector alignment",
        toolingMasterGlobalId: masterId,
        toolingRevisionGlobalId: toolingRevisionId,
        toolingRevisionSnapshotHash: revision().snapshotHash,
        traceId: "trace-p6-05-engineering-controls",
        trialReference: {
          reasonCode: "trial_context_unavailable",
          state: "unavailable",
        },
        versionKeyHash: "3".repeat(64),
      },
    ],
    health: {
      calibration: {
        reasonCode: "shot_count_calibration_policy_unavailable",
        state: "unavailable",
      },
      editableIn: "ERPNEXT",
      healthScore: {
        reasonCode: "tooling_health_policy_unavailable",
        state: "unavailable",
      },
      maintenance: {
        reasonCode: "erp_maintenance_projection_unavailable",
        state: "unavailable",
      },
      shotCount: {
        reasonCode: "erp_shot_count_unavailable",
        state: "unavailable",
      },
      sourceSystem: "ERPNEXT",
      state: "unavailable",
    },
    permissions: {
      approveProcessBaseline: false,
      createCapacityScenario: true,
      createCustomerStandard: true,
      createTrialActual: false,
      editHealth: false,
      reviseDefect: true,
      transitionGate: false,
      transitionToolingLifecycle: false,
      view: true,
    },
    process: {
      approvedBaseline: {
        reasonCode: "approved_trial_evidence_unavailable",
        state: "unavailable",
      },
      comparisons: [
        {
          actualValue: null,
          delta: null,
          metricCode: "cycle_time",
          percentDelta: null,
          referenceLayer: "customer_standard",
          referenceValue: "35",
          ruleGlobalId: null,
          ruleSnapshotHash: null,
          ruleVersion: null,
          state: "not_measured",
          unit: "s",
          visualSemantics: {
            reasonCode: "variance_exception_color_policy_unavailable",
            state: "unavailable",
          },
        },
      ],
      customerStandardRevisions: [
        {
          context: {
            approvalEventGlobalId: null,
            approvalEventHash: null,
            globalId: toolingRevisionId,
            kind: "tooling_revision_specification",
            releasedDocument: null,
            snapshotHash: revision().snapshotHash,
          },
          createdAt: "2026-08-08T12:05:00Z",
          createdByUserId: "tooling.engineer@example.invalid",
          effectiveFrom: "2026-08-08",
          globalId: processProfileRevisionId,
          layer: "customer_standard",
          metrics: [
            {
              code: "cycle_time",
              comparisonRule: null,
              globalId: processMetricId,
              numericValue: "35",
              textValue: null,
              unit: "s",
              valueKind: "numeric",
            },
          ],
          predecessorGlobalId: null,
          predecessorSnapshotHash: null,
          profileGlobalId: processProfileId,
          profileVersion: 1,
          projectGlobalId: projectId,
          reason: "Customer cycle requirement",
          requestId: processProfileRevisionId,
          schemaVersion: 1,
          snapshotHash: "c".repeat(64),
          tenantId: "tenant.synthetic",
          toolingMasterGlobalId: masterId,
          toolingRevisionGlobalId: toolingRevisionId,
          toolingRevisionSnapshotHash: revision().snapshotHash,
          traceId: "trace-p6-05-engineering-controls",
          versionKeyHash: "4".repeat(64),
        },
      ],
      trialActual: {
        reasonCode: "trial_context_unavailable",
        state: "not_measured",
      },
    },
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
  };
}

function requestIdentity(route: Route): string {
  const requestId = route.request().headers()["x-request-id"] ?? "";
  expect(requestId).toMatch(requestIdPattern);
  return requestId;
}

async function fulfillJson(
  route: Route,
  body: unknown,
  status = 200,
): Promise<void> {
  await route.fulfill({
    body: JSON.stringify(body),
    headers: {
      "Cache-Control": "private, no-store",
      "Content-Type": "application/json",
      ...(route.request().headers()["idempotency-key"]
        ? { "Idempotency-Replayed": "false" }
        : {}),
      "X-Request-ID": requestIdentity(route),
      "X-Trace-ID": "trace-p6-03-tooling-revision-browser",
    },
    status,
  });
}

async function installSession(page: Page, locale: TestLocale): Promise<void> {
  await page.route(sessionEndpoint, async (route) => {
    await fulfillJson(route, {
      allowedLanguages: ["en", "zh", "zh-TW"],
      catalog: { language: locale, messages: {}, version: "5".repeat(64) },
      csrfToken,
      language: locale,
      preferences: { navigationCollapsed: false },
      userId: "tooling.engineer@example.invalid",
    });
  });
}

function exactToolAssetProjectionCollection(authoritative: boolean) {
  const collection = toolAssetProjectionCollection();
  const item = collection.items[0];
  if (!item?.currentTruth) {
    throw new Error("The authoritative Tool Asset projection is required.");
  }
  if (!authoritative) {
    return { ...collection, items: [], projectGlobalId: projectId };
  }
  const values = { ...item.currentTruth.values, toolingSetGlobalId: setId };
  return {
    ...collection,
    projectGlobalId: projectId,
    items: [
      {
        ...item,
        scopeGlobalId: setId,
        values,
        currentTruth: { ...item.currentTruth, values },
      },
    ],
  };
}

async function installApi(
  page: Page,
  options: {
    acceptanceReady?: boolean;
    authoritativeAssetProjection?: boolean;
    partRecorded?: boolean;
  } = {},
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  await page.route(projectEndpoint, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    observed.push({
      idempotencyKey: request.headers()["idempotency-key"],
      method: request.method(),
      path,
      payload: request.method() === "POST" ? request.postDataJSON() : null,
    });
    if (request.method() === "POST") {
      expect(request.headers()["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(request.headers()["idempotency-key"]).toMatch(/^tooling-/u);
    }
    if (path.includes("/tooling-list/preferences/")) {
      await fulfillJson(route, toolingListPreference());
      return;
    }
    if (path.endsWith("/tooling-list")) {
      await fulfillJson(route, toolingListPage());
      return;
    }
    if (path.endsWith("/erp-projections")) {
      expect(new URL(request.url()).searchParams.get("kind")).toBe(
        "tool_asset_status",
      );
      await fulfillJson(
        route,
        exactToolAssetProjectionCollection(
          options.authoritativeAssetProjection === true,
        ),
      );
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/acceptance-assets`)) {
      await fulfillJson(route, acceptanceAssetContext());
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/acceptance-revisions`)) {
      await fulfillJson(
        route,
        { acceptanceEvidence: acceptanceEvidence(true) },
        201,
      );
      return;
    }
    if (
      path.endsWith(`/tooling/${masterId}/asset-requests/${assetRequestId}`)
    ) {
      await fulfillJson(route, toolAssetRequest());
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/sets/${setId}/asset-requests`)) {
      await fulfillJson(route, toolAssetRequest(), 201);
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/asset-requests`)) {
      await fulfillJson(route, toolAssetRequestCollection());
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/sets/${setId}/revision-binding`)) {
      await fulfillJson(route, setDetail(true), 201);
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/sets/${setId}`)) {
      await fulfillJson(route, setDetail());
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/sets`)) {
      const collection = setCollection();
      await fulfillJson(
        route,
        options.acceptanceReady
          ? { ...collection, items: [setDetail(true).toolingSet] }
          : collection,
      );
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/defect-revisions`)) {
      const current = engineeringControls().defectRevisions[0];
      if (!current) throw new Error("The defect fixture is required.");
      await fulfillJson(
        route,
        {
          defect: {
            ...current,
            defectVersion: 2,
            predecessorGlobalId: current.globalId,
            predecessorSnapshotHash: current.snapshotHash,
            snapshotHash: "4".repeat(64),
            versionKeyHash: "5".repeat(64),
          },
        },
        201,
      );
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/process-profile-revisions`)) {
      const current =
        engineeringControls().process.customerStandardRevisions[0];
      if (!current) throw new Error("The process profile fixture is required.");
      await fulfillJson(
        route,
        {
          profile: {
            ...current,
            predecessorGlobalId: current.globalId,
            predecessorSnapshotHash: current.snapshotHash,
            profileVersion: 2,
            snapshotHash: "6".repeat(64),
            versionKeyHash: "7".repeat(64),
          },
        },
        201,
      );
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/capacity-scenario-revisions`)) {
      const current = engineeringControls().capacityScenarioRevisions[0];
      if (!current) throw new Error("The capacity fixture is required.");
      await fulfillJson(
        route,
        {
          scenario: {
            ...current,
            predecessorGlobalId: current.globalId,
            predecessorSnapshotHash: current.snapshotHash,
            scenarioVersion: 2,
            snapshotHash: "9".repeat(64),
            versionKeyHash: "a".repeat(64),
          },
        },
        201,
      );
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/engineering-controls`)) {
      await fulfillJson(route, engineeringControls());
      return;
    }
    if (
      path.endsWith(
        `/manufacturing-plans/${manufacturingPlanRevisionId}/milestones/${manufacturingMilestoneId}/observations`,
      )
    ) {
      await fulfillJson(
        route,
        { observation: manufacturingObservation() },
        201,
      );
      return;
    }
    if (path.endsWith(`/manufacturing-plans/${manufacturingPlanRevisionId}`)) {
      await fulfillJson(route, manufacturingDetail());
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/manufacturing-plans`)) {
      await fulfillJson(
        route,
        request.method() === "POST"
          ? {
              designReleaseEvidence:
                manufacturingCollection().items[0]?.designReleaseEvidence,
              plan: manufacturingPlan(),
            }
          : manufacturingCollection(),
        request.method() === "POST" ? 201 : 200,
      );
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/revisions/${toolingRevisionId}`)) {
      await fulfillJson(route, revisionDetail());
      return;
    }
    if (path.endsWith(`/tooling/${masterId}/revisions`)) {
      await fulfillJson(
        route,
        request.method() === "POST" ? revisionDetail() : revisionCollection(),
        request.method() === "POST" ? 201 : 200,
      );
      return;
    }
    if (path.endsWith("/controlled-specification")) {
      await fulfillJson(
        route,
        partContext(
          request.method() === "POST" || options.partRecorded !== false,
        ),
        request.method() === "POST" ? 201 : 200,
      );
      return;
    }
    if (path.endsWith(`/tooling-process-chains/${processChainRevisionId}`)) {
      await fulfillJson(route, processChain());
      return;
    }
    if (path.endsWith("/tooling-process-chains")) {
      await fulfillJson(
        route,
        request.method() === "POST" ? processChain() : chainCollection(),
        request.method() === "POST" ? 201 : 200,
      );
      return;
    }
    if (path.endsWith(`/tooling/${masterId}`)) {
      await fulfillJson(route, cockpit());
      return;
    }
    await route.abort();
  });
  return observed;
}

async function openWorkspace(page: Page, locale: TestLocale): Promise<void> {
  await page.goto(`/projects/${projectId}/tooling/${masterId}?lang=${locale}`, {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator(".route-loading")).toHaveCount(0);
  await expect(page.locator("#tooling-revision-workspace")).toBeVisible();
  await expect(page.getByText("R1 · 1")).toBeVisible();
  await expect(page.getByText("PA66", { exact: true })).toBeVisible();
  await expect(page.getByText("SET-REV-001").first()).toBeVisible();
}

async function expectAxeClean(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

function executionDetailFixture(
  state: "synthetic_verified" | "partially_succeeded" | "succeeded",
) {
  const value = toolAssetExecutionDetail(state);
  return {
    ...value,
    request: {
      ...value.request,
      source: {
        ...value.request.source,
        projectGlobalId: projectId,
        toolingMasterGlobalId: masterId,
        toolingSetGlobalId: setId,
        acceptanceRevisionGlobalId: acceptanceRevisionId,
      },
    },
  };
}

function executionCollectionFixture(
  detail = executionDetailFixture("synthetic_verified"),
) {
  const value = toolAssetExecutionCollection(detail);
  const context = toolAssetExecutionContext();
  const exactContext = {
    ...context,
    source: {
      ...context.source,
      projectGlobalId: projectId,
      toolingMasterGlobalId: masterId,
      toolingSetGlobalId: setId,
      acceptanceRevisionGlobalId: acceptanceRevisionId,
    },
  };
  return {
    ...value,
    projectGlobalId: projectId,
    toolingMasterGlobalId: masterId,
    toolingSetGlobalId: setId,
    commandContexts: { create_tool_asset: exactContext },
    items: value.items.map((item) => ({
      ...item,
      request: { ...item.request, source: exactContext.source },
    })),
  };
}

async function installExecutionApi(
  page: Page,
  state: "synthetic_verified" | "partially_succeeded" | "succeeded",
): Promise<ObservedRequest[]> {
  const observed: ObservedRequest[] = [];
  const detail = executionDetailFixture(state);
  const collection = executionCollectionFixture(detail);
  await page.route(projectEndpoint, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const base = `/projects/${projectId}/tooling/${masterId}/sets/${setId}/asset-execution-requests`;
    if (!url.pathname.includes("/asset-execution-requests")) {
      await route.fallback();
      return;
    }
    observed.push({
      idempotencyKey: request.headers()["idempotency-key"],
      method: request.method(),
      path: url.pathname,
      payload: request.method() === "POST" ? request.postDataJSON() : null,
    });
    if (url.pathname.endsWith(base) && request.method() === "GET") {
      expect(url.searchParams.get("acceptanceRevisionGlobalId")).toBe(
        acceptanceRevisionId,
      );
      await fulfillJson(route, collection);
      return;
    }
    if (
      url.pathname.endsWith(`${base}/${toolAssetExecutionRequestId}`) &&
      request.method() === "GET"
    ) {
      await fulfillJson(route, detail);
      return;
    }
    if (
      url.pathname.endsWith(`${base}:create`) &&
      request.method() === "POST"
    ) {
      expect(request.headers()["x-frappe-csrf-token"]).toBe(csrfToken);
      expect(request.headers()["idempotency-key"]).toMatch(/^tool-asset-/u);
      const context = collection.commandContexts.create_tool_asset;
      expect(request.postDataJSON()).toEqual({
        acceptanceRevisionGlobalId: acceptanceRevisionId,
        expectedSourceHash: context.expectedSourceHash,
        expectedApprovalHash: context.expectedApprovalHash,
        expectedMappingExpectationHash: context.expectedMappingExpectationHash,
        expectedProfileSnapshotHash: context.expectedProfileSnapshotHash,
        acknowledgement:
          "I confirm this request may create one formal ERP Asset only from the exact physical Tooling Set, separate business approval, mapping state, and execution profile.",
      });
      await fulfillJson(route, collection.items[0], 201);
      return;
    }
    throw new Error(
      `Unhandled P8-05 browser request: ${request.method()} ${url.pathname}${url.search}`,
    );
  });
  return observed;
}

async function openExecutionInspector(
  page: Page,
  locale: TestLocale,
): Promise<void> {
  await openWorkspace(page, locale);
  const inspector = page
    .locator("#tooling-acceptance-asset-workspace .panel")
    .filter({
      hasText:
        locale === "en"
          ? "Tool Asset execution inspector"
          : locale === "zh"
            ? "工装资产执行检查器"
            : "工裝資產執行檢查器",
    })
    .first();
  await inspector.scrollIntoViewIfNeeded();
  await expect(inspector).toBeVisible();
}

test.describe("P8-05 live Tool Asset execution inspector", () => {
  test("keeps the operation-specific command Project-first and browser target-network-free", async ({
    page,
  }) => {
    await installSession(page, "en");
    await installApi(page, { acceptanceReady: true });
    const observed = await installExecutionApi(page, "synthetic_verified");
    await openExecutionInspector(page, "en");
    const inspector = page
      .locator("#tooling-acceptance-asset-workspace .panel")
      .filter({ hasText: "Tool Asset execution inspector" })
      .first();
    await expect(
      inspector.locator('[data-visual-primary="true"]:visible'),
    ).toHaveCount(1);
    await page
      .getByRole("button", { name: "Review Tool Asset request" })
      .click();
    await expect(
      page.getByRole("dialog", { name: "Review exact Tool Asset request" }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Request Tool Asset execution" })
      .click();
    await expect
      .poll(() => observed.filter((item) => item.method === "POST").length)
      .toBe(1);
    expect(
      observed.every((item) => item.path.startsWith("/api/npi/v1/projects/")),
    ).toBe(true);
    await expectAxeClean(page);
  });

  for (const state of [
    "synthetic_verified",
    "partially_succeeded",
    "succeeded",
  ] as const) {
    test(`renders truthful ${state} state without retry, reconcile or approval controls`, async ({
      page,
    }) => {
      await installSession(page, "en");
      await installApi(page, {
        acceptanceReady: true,
        authoritativeAssetProjection: state === "succeeded",
      });
      await installExecutionApi(page, state);
      await openExecutionInspector(page, "en");
      const inspector = page
        .locator("#tooling-acceptance-asset-workspace .panel")
        .filter({ hasText: "Tool Asset execution inspector" })
        .first();
      await expect(
        inspector.getByRole("button", {
          name: /retry|reconcile|submit|approve/iu,
        }),
      ).toHaveCount(0);
      if (state === "succeeded")
        await expect(inspector.getByText("ASSET-00042")).toBeVisible();
      else await expect(inspector.getByText("ASSET-00042")).toHaveCount(0);
      await expectNoMixedLanguage(page, "en");
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
    });
  }
});

const p805Visuals = [
  {
    locale: "en",
    state: "synthetic_verified",
    width: 1366,
    height: 768,
    zoom: 1.25,
    name: "p8-05-tool-asset-synthetic-en-1366x768-125",
  },
  {
    locale: "zh",
    state: "partially_succeeded",
    width: 1920,
    height: 1080,
    zoom: 1.5,
    name: "p8-05-tool-asset-partial-zh-1920x1080-150",
  },
  {
    locale: "zh-TW",
    state: "succeeded",
    width: 1920,
    height: 1080,
    zoom: 1.25,
    name: "p8-05-tool-asset-authoritative-zh-TW-1920x1080-125",
  },
] as const;

test.describe("@visual P8-05 Tool Asset execution inspector", () => {
  for (const visual of p805Visuals) {
    test(visual.name, async ({ page }) => {
      await installSession(page, visual.locale);
      await installApi(page, {
        acceptanceReady: true,
        authoritativeAssetProjection: visual.state === "succeeded",
      });
      await installExecutionApi(page, visual.state);
      await page.setViewportSize(
        effectiveViewport(
          { height: visual.height, width: visual.width },
          visual.zoom,
        ),
      );
      await page.emulateMedia({
        colorScheme: "light",
        reducedMotion: "reduce",
      });
      await openExecutionInspector(page, visual.locale);
      await expectNoMixedLanguage(page, visual.locale);
      await expectNoDocumentOverflow(page);
      await expectIndustrialComputedStyles(page);
      await expectAxeClean(page);
      await page.addStyleTag({
        content:
          "*, *::before, *::after { animation-delay: 0s !important; animation-duration: 0s !important; transition: none !important; }",
      });
      await page.evaluate(async () => document.fonts.ready);
      await expect(page).toHaveScreenshot(`${visual.name}.png`, {
        fullPage: false,
      });
    });
  }
});
