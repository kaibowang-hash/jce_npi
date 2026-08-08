import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ComponentProps,
} from "react";

import type { ReportWorkspaceDirty } from "../app/workspace-navigation";
import type {
  CreatePartControlledSpecificationCommand,
  CreateToolingProcessChainRevisionCommand,
  CreateToolingRevisionCommand,
  EngineeringPartSummaryViewModel,
  PartControlledSpecificationContextViewModel,
  PartControlledSpecificationKind,
  ToolingApplicabilitySummaryViewModel,
  ToolingCommandContext,
  ToolingDataSource,
  ToolingProcessChainCollectionViewModel,
  ToolingRevisionCollectionViewModel,
  ToolingRevisionDetailViewModel,
  ToolingRevisionViewModel,
} from "../api/tooling-data-source";
import { ToolingRequestCancelledError } from "../api/tooling-data-source";
import { toRequestFailure, type RequestFailure } from "../api/http";
import { RequestFailurePanel } from "../components/problem-details-panel";
import {
  DefinitionList,
  Panel,
  SemanticStatus,
} from "../components/primitives";
import { formatNumber } from "../i18n/formatters";
import { useI18n } from "../i18n/runtime";
import { Button, Select, TextInput } from "../ui-adapters/npi-ui";

type ResourceState<T> =
  | { kind: "loading" }
  | { kind: "loaded"; value: T }
  | { kind: "failed"; failure: RequestFailure };
type EditorKind = "revision" | "part-specification" | "process-chain";
type CommandState =
  | { kind: "idle" }
  | { kind: "processing"; label: string }
  | { kind: "failed"; failure: RequestFailure };

interface RevisionDraft {
  revisionLabel: string;
  reason: string;
  toolingType: string;
  moldBaseMaterial: string;
  coreMaterial: string;
  hardness: string;
  surfaceTreatment: string;
  cavityCount: string;
  hotRunner: string;
  length: string;
  width: string;
  height: string;
  weight: string;
  clampTonnage: string;
  tieBarSpacingX: string;
  tieBarSpacingY: string;
  injectionCapacity: string;
  machineType: string;
  targetCycle: string;
  targetLife: string;
  warranty: string;
  customerStandard: string;
  interfaceRequirement: string;
  spareParts: string;
  deliveryDocuments: string;
  cavityIdentifier: string;
  applicabilityId: string;
  structuralState: "enabled" | "sealed";
  insertCode: string;
  insertVersion: string;
  changeoverDuration: string;
  validationState: "not_validated" | "validated";
  validationReason: string;
  externalIdentityValue: string;
  externalIdentityRawValue: string;
  externalIdentitySourceObjectId: string;
  designDocumentRevisionId: string;
  designDocumentSnapshotHash: string;
}

interface PartSpecificationDraft {
  kind: PartControlledSpecificationKind;
  normalizedValue: string;
  rawValue: string;
  sourceObjectId: string;
  effectiveFrom: string;
  unit: string;
}

interface ProcessChainDraft {
  processChainGlobalId: string;
  reason: string;
  firstRevisionId: string;
  secondRevisionId: string;
  inputPartRevisionId: string;
  intermediatePartRevisionId: string;
  outputPartRevisionId: string;
  firstMachineType: string;
  secondMachineType: string;
  firstClampTonnage: string;
  secondClampTonnage: string;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function revisionDraft(
  applicability: readonly ToolingApplicabilitySummaryViewModel[],
): RevisionDraft {
  return {
    applicabilityId: applicability[0]?.globalId ?? "",
    cavityCount: "1",
    cavityIdentifier: "C01",
    clampTonnage: "0",
    coreMaterial: "",
    customerStandard: "",
    deliveryDocuments: "",
    designDocumentRevisionId: "",
    designDocumentSnapshotHash: "",
    externalIdentityRawValue: "",
    externalIdentitySourceObjectId: "",
    externalIdentityValue: "",
    hardness: "0",
    height: "0",
    hotRunner: "",
    injectionCapacity: "0",
    insertCode: "",
    insertVersion: "1",
    interfaceRequirement: "",
    length: "0",
    machineType: "",
    moldBaseMaterial: "",
    reason: "",
    revisionLabel: "",
    spareParts: "",
    structuralState: "enabled",
    surfaceTreatment: "",
    targetCycle: "0",
    targetLife: "0",
    tieBarSpacingX: "0",
    tieBarSpacingY: "0",
    toolingType: "",
    validationReason: "",
    validationState: "not_validated",
    warranty: "",
    weight: "0",
    width: "0",
    changeoverDuration: "0",
  };
}

function partSpecificationDraft(): PartSpecificationDraft {
  return {
    effectiveFrom: today(),
    kind: "material_family",
    normalizedValue: "",
    rawValue: "",
    sourceObjectId: "",
    unit: "",
  };
}

function processChainDraft(
  revisions: readonly ToolingRevisionViewModel[],
  parts: readonly EngineeringPartSummaryViewModel[],
): ProcessChainDraft {
  const revisionId = revisions.at(-1)?.globalId ?? "";
  const partRevisionId = parts[0]?.currentRevision.globalId ?? "";
  return {
    firstClampTonnage: "0",
    firstMachineType: "",
    firstRevisionId: revisionId,
    inputPartRevisionId: partRevisionId,
    intermediatePartRevisionId: partRevisionId,
    outputPartRevisionId: partRevisionId,
    processChainGlobalId: "",
    reason: "",
    secondClampTonnage: "0",
    secondMachineType: "",
    secondRevisionId: revisionId,
  };
}

function canRetry(failure: RequestFailure): boolean {
  return (
    failure.kind === "network" ||
    Boolean(failure.problem?.retryable) ||
    failure.problem?.status === 409
  );
}

function LabeledTextInput({
  label,
  ...properties
}: ComponentProps<typeof TextInput> & { label: string }): React.JSX.Element {
  return (
    <label>
      <span>{label}</span>
      <TextInput {...properties} />
    </label>
  );
}

function measurement(value: string, unit: string) {
  return { source: "Engineering", unit, value };
}

function list(value: string): readonly string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function unavailableLabel(
  t: ReturnType<typeof useI18n>["t"],
  reason: string,
): string {
  switch (reason) {
    case "lifecycle_policy_unavailable":
      return t("Lifecycle policy is not approved.");
    case "formal_supplier_unavailable":
      return t("Formal Supplier is not delivered yet.");
    case "erp_projection_unavailable":
      return t("ERPNext location and Asset projection are unavailable.");
    case "combined_trial_not_delivered":
      return t("Combined Trial truth is not delivered yet.");
    case "automatic_impact_not_delivered":
      return t("Automatic impact analysis is not delivered yet.");
    default:
      return t("Controlled Part specification is not recorded.");
  }
}

function specificationKindLabel(
  t: ReturnType<typeof useI18n>["t"],
  value: PartControlledSpecificationKind,
): string {
  switch (value) {
    case "material_family":
      return t("Material family");
    case "grade":
      return t("Material grade");
    case "trademark":
      return t("Trademark");
    case "color":
      return t("Color");
    case "color_masterbatch":
      return t("Color masterbatch");
    case "fda_compliance":
      return t("FDA compliance");
    case "regulatory_compliance":
      return t("Regulatory compliance");
    case "secondary_process":
      return t("Secondary process");
  }
}

export default function ToolingRevisionWorkspace({
  applicability,
  dataSource,
  masterId,
  parts,
  projectId,
  reportWorkspaceDirty,
}: {
  applicability: readonly ToolingApplicabilitySummaryViewModel[];
  dataSource: ToolingDataSource;
  masterId: string;
  parts: readonly EngineeringPartSummaryViewModel[];
  projectId: string;
  reportWorkspaceDirty?: ReportWorkspaceDirty | undefined;
}): React.JSX.Element {
  const { locale, sessionCommandContext, t } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const [revisions, setRevisions] = useState<
    ResourceState<ToolingRevisionCollectionViewModel>
  >({ kind: "loading" });
  const [detail, setDetail] = useState<
    ResourceState<ToolingRevisionDetailViewModel> | { kind: "idle" }
  >({ kind: "idle" });
  const [chains, setChains] = useState<
    ResourceState<ToolingProcessChainCollectionViewModel>
  >({ kind: "loading" });
  const [selectedRevisionId, setSelectedRevisionId] = useState<string | null>(
    null,
  );
  const [selectedPartId, setSelectedPartId] = useState<string>(
    parts[0]?.globalId ?? "",
  );
  const [partSpecification, setPartSpecification] = useState<
    | ResourceState<PartControlledSpecificationContextViewModel>
    | { kind: "idle" }
  >(parts[0] ? { kind: "loading" } : { kind: "idle" });
  const [editor, setEditor] = useState<EditorKind | null>(null);
  const [revisionForm, setRevisionForm] = useState<RevisionDraft>(() =>
    revisionDraft(applicability),
  );
  const [partForm, setPartForm] = useState<PartSpecificationDraft>(() =>
    partSpecificationDraft(),
  );
  const [chainForm, setChainForm] = useState<ProcessChainDraft>(() =>
    processChainDraft([], parts),
  );
  const [formError, setFormError] = useState<string | null>(null);
  const [command, setCommand] = useState<CommandState>({ kind: "idle" });
  const retryCommand = useRef<(() => void) | null>(null);
  const editorTrigger = useRef<HTMLElement | null>(null);
  const selectedPart = parts.find((item) => item.globalId === selectedPartId);
  const loadedRevisions = revisions.kind === "loaded" ? revisions.value : null;
  const revisionItems = loadedRevisions?.items ?? [];

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      dataSource.loadToolingRevisions(projectId, masterId, controller.signal),
      dataSource.loadToolingProcessChains(projectId, controller.signal),
    ])
      .then(([revisionValue, chainValue]) => {
        if (controller.signal.aborted) return;
        setRevisions({ kind: "loaded", value: revisionValue });
        setChains({ kind: "loaded", value: chainValue });
        const revisionId = revisionValue.items.at(-1)?.globalId ?? null;
        setSelectedRevisionId(revisionId);
        setDetail(revisionId ? { kind: "loading" } : { kind: "idle" });
        setChainForm(processChainDraft(revisionValue.items, parts));
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          error instanceof ToolingRequestCancelledError
        )
          return;
        const failure = toRequestFailure(error);
        setRevisions({ kind: "failed", failure });
        setChains({ kind: "failed", failure });
      });
    return () => {
      controller.abort();
    };
  }, [attempt, dataSource, masterId, parts, projectId]);

  useEffect(() => {
    if (!selectedRevisionId) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadToolingRevision(
        projectId,
        masterId,
        selectedRevisionId,
        controller.signal,
      )
      .then((value) => {
        if (!controller.signal.aborted) setDetail({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (
          !controller.signal.aborted &&
          !(error instanceof ToolingRequestCancelledError)
        )
          setDetail({ kind: "failed", failure: toRequestFailure(error) });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, masterId, projectId, selectedRevisionId]);

  useEffect(() => {
    if (!selectedPart) return undefined;
    const controller = new AbortController();
    void dataSource
      .loadPartControlledSpecification(
        projectId,
        selectedPart.globalId,
        selectedPart.currentRevision.globalId,
        controller.signal,
      )
      .then((value) => {
        if (!controller.signal.aborted)
          setPartSpecification({ kind: "loaded", value });
      })
      .catch((error: unknown) => {
        if (
          !controller.signal.aborted &&
          !(error instanceof ToolingRequestCancelledError)
        )
          setPartSpecification({
            kind: "failed",
            failure: toRequestFailure(error),
          });
      });
    return () => {
      controller.abort();
    };
  }, [dataSource, projectId, selectedPart]);

  useEffect(() => {
    if (!reportWorkspaceDirty) return undefined;
    if (!editor) {
      reportWorkspaceDirty(null);
      return undefined;
    }
    reportWorkspaceDirty({
      objectIdentity:
        editor === "part-specification"
          ? selectedPartId
          : `${masterId}:tooling-revision`,
      returnFocusTarget: () => editorTrigger.current,
      version: "unsaved-tooling-revision-context",
    });
    return () => {
      reportWorkspaceDirty(null);
    };
  }, [editor, masterId, reportWorkspaceDirty, selectedPartId]);

  const commandContext = useCallback(
    (prefix: string, signal: AbortSignal): ToolingCommandContext | null => {
      if (!sessionCommandContext) return null;
      return {
        ...sessionCommandContext,
        idempotencyKey: `${prefix}-${globalThis.crypto.randomUUID()}`,
        signal,
      };
    },
    [sessionCommandContext],
  );

  const runCommand = useCallback(
    <T,>(
      label: string,
      operation: (context: ToolingCommandContext) => Promise<T>,
      accept: (value: T) => void,
    ): void => {
      const execute = (): void => {
        const controller = new AbortController();
        const context = commandContext("tooling-revision", controller.signal);
        if (!context) return;
        setCommand({ kind: "processing", label });
        void operation(context)
          .then((value) => {
            accept(value);
            setCommand({ kind: "idle" });
            setEditor(null);
            setFormError(null);
          })
          .catch((error: unknown) => {
            if (
              !controller.signal.aborted &&
              !(error instanceof ToolingRequestCancelledError)
            )
              setCommand({ kind: "failed", failure: toRequestFailure(error) });
          });
      };
      retryCommand.current = execute;
      execute();
    },
    [commandContext],
  );

  const submitRevision = (): void => {
    const application = applicability.find(
      (item) => item.globalId === revisionForm.applicabilityId,
    );
    const requiredText = [
      revisionForm.revisionLabel,
      revisionForm.reason,
      revisionForm.toolingType,
      revisionForm.moldBaseMaterial,
      revisionForm.coreMaterial,
      revisionForm.surfaceTreatment,
      revisionForm.hotRunner,
      revisionForm.machineType,
      revisionForm.warranty,
      revisionForm.customerStandard,
      revisionForm.interfaceRequirement,
      revisionForm.cavityIdentifier,
    ];
    const numeric = [
      revisionForm.hardness,
      revisionForm.length,
      revisionForm.width,
      revisionForm.height,
      revisionForm.weight,
      revisionForm.clampTonnage,
      revisionForm.tieBarSpacingX,
      revisionForm.tieBarSpacingY,
      revisionForm.injectionCapacity,
      revisionForm.targetCycle,
      revisionForm.targetLife,
    ];
    if (
      !application ||
      requiredText.some((value) => !value.trim()) ||
      numeric.some((value) => !/^\d+(?:\.\d+)?$/u.test(value)) ||
      !/^\d+$/u.test(revisionForm.cavityCount) ||
      Number(revisionForm.cavityCount) < 1
    ) {
      setFormError(t("Complete the exact Revision specification and cavity."));
      return;
    }
    if (
      revisionForm.validationState === "validated" &&
      revisionForm.insertCode.trim() &&
      !revisionForm.validationReason.trim()
    ) {
      setFormError(t("Validated insert evidence requires a reason."));
      return;
    }
    if (
      revisionForm.insertCode.trim() &&
      (!/^\d+$/u.test(revisionForm.insertVersion) ||
        Number(revisionForm.insertVersion) < 1 ||
        !/^\d+(?:\.\d+)?$/u.test(revisionForm.changeoverDuration))
    ) {
      setFormError(t("Complete all fields for the optional insert."));
      return;
    }
    const externalIdentityFields = [
      revisionForm.externalIdentityValue,
      revisionForm.externalIdentityRawValue,
      revisionForm.externalIdentitySourceObjectId,
    ];
    if (
      externalIdentityFields.some((value) => value.trim()) &&
      externalIdentityFields.some((value) => !value.trim())
    ) {
      setFormError(
        t("Complete all fields for the optional external identity."),
      );
      return;
    }
    const designDocumentFields = [
      revisionForm.designDocumentRevisionId,
      revisionForm.designDocumentSnapshotHash,
    ];
    if (
      designDocumentFields.some((value) => value.trim()) &&
      designDocumentFields.some((value) => !value.trim())
    ) {
      setFormError(
        t("Complete both fields for the optional Design Document Revision."),
      );
      return;
    }
    const latest = revisionItems.at(-1);
    const payload: CreateToolingRevisionCommand = {
      ...(latest ? { expectedVersion: latest.revisionNumber } : {}),
      cavities: [
        {
          cavityIdentifier: revisionForm.cavityIdentifier.trim(),
          partRevisionGlobalId: application.part.globalId,
          structuralState: revisionForm.structuralState,
          toolingApplicabilityGlobalId: application.globalId,
        },
      ],
      designDocumentRevisions: revisionForm.designDocumentRevisionId.trim()
        ? [
            {
              globalId: revisionForm.designDocumentRevisionId.trim(),
              snapshotHash: revisionForm.designDocumentSnapshotHash.trim(),
            },
          ]
        : [],
      externalIdentities: revisionForm.externalIdentityValue.trim()
        ? [
            {
              effectiveFrom: today(),
              identityType: "customer",
              rawValue: revisionForm.externalIdentityRawValue.trim(),
              sourceObjectId:
                revisionForm.externalIdentitySourceObjectId.trim(),
              sourceSystem: "NPI_ONE",
              value: revisionForm.externalIdentityValue.trim(),
            },
          ]
        : [],
      inserts: revisionForm.insertCode.trim()
        ? [
            {
              changeoverDuration: measurement(
                revisionForm.changeoverDuration,
                "min",
              ),
              insertCode: revisionForm.insertCode.trim(),
              insertVersion: Number(revisionForm.insertVersion),
              partRevisionGlobalId: application.part.globalId,
              toolingApplicabilityGlobalId: application.globalId,
              validationState: revisionForm.validationState,
              ...(revisionForm.validationState === "validated"
                ? { validationReason: revisionForm.validationReason.trim() }
                : {}),
            },
          ]
        : [],
      reason: revisionForm.reason.trim(),
      revisionLabel: revisionForm.revisionLabel.trim(),
      specification: {
        cavityCount: Number(revisionForm.cavityCount),
        clampTonnage: measurement(revisionForm.clampTonnage, "t"),
        coreMaterial: revisionForm.coreMaterial.trim(),
        customerStandard: revisionForm.customerStandard.trim(),
        deliveryDocuments: list(revisionForm.deliveryDocuments),
        hardness: measurement(revisionForm.hardness, "HRC"),
        height: measurement(revisionForm.height, "mm"),
        hotRunner: revisionForm.hotRunner.trim(),
        injectionCapacity: measurement(revisionForm.injectionCapacity, "g"),
        interfaceRequirement: revisionForm.interfaceRequirement.trim(),
        length: measurement(revisionForm.length, "mm"),
        machineType: revisionForm.machineType.trim(),
        moldBaseMaterial: revisionForm.moldBaseMaterial.trim(),
        spareParts: list(revisionForm.spareParts),
        surfaceTreatment: revisionForm.surfaceTreatment.trim(),
        targetCycle: measurement(revisionForm.targetCycle, "s"),
        targetLife: measurement(revisionForm.targetLife, "cycles"),
        tieBarSpacingX: measurement(revisionForm.tieBarSpacingX, "mm"),
        tieBarSpacingY: measurement(revisionForm.tieBarSpacingY, "mm"),
        toolingType: revisionForm.toolingType.trim(),
        warranty: revisionForm.warranty.trim(),
        weight: measurement(revisionForm.weight, "kg"),
        width: measurement(revisionForm.width, "mm"),
      },
    };
    runCommand(
      t("Creating immutable Tooling Revision"),
      (context) =>
        dataSource.createToolingRevision(projectId, masterId, payload, context),
      (value) => {
        setDetail({ kind: "loaded", value });
        setSelectedRevisionId(value.revision.globalId);
        setRevisions((current) =>
          current.kind === "loaded"
            ? {
                kind: "loaded",
                value: {
                  ...current.value,
                  items: [...current.value.items, value.revision],
                },
              }
            : current,
        );
      },
    );
  };

  const submitPartSpecification = (): void => {
    if (
      !selectedPart ||
      !partForm.normalizedValue.trim() ||
      !partForm.rawValue.trim() ||
      !partForm.sourceObjectId.trim()
    ) {
      setFormError(t("Complete the controlled Part specification item."));
      return;
    }
    const payload: CreatePartControlledSpecificationCommand = {
      externalIdentities: [],
      items: [
        {
          effectiveFrom: partForm.effectiveFrom,
          kind: partForm.kind,
          normalizedValue: partForm.normalizedValue.trim(),
          rawValue: partForm.rawValue.trim(),
          sourceObjectId: partForm.sourceObjectId.trim(),
          sourceSystem: "NPI_ONE",
          ...(partForm.unit.trim() ? { unit: partForm.unit.trim() } : {}),
        },
      ],
    };
    runCommand(
      t("Recording controlled Part specification"),
      (context) =>
        dataSource.createPartControlledSpecification(
          projectId,
          selectedPart.globalId,
          selectedPart.currentRevision.globalId,
          payload,
          context,
        ),
      (value) => {
        setPartSpecification({ kind: "loaded", value });
      },
    );
  };

  const submitProcessChain = (): void => {
    const required = [
      chainForm.reason,
      chainForm.firstRevisionId,
      chainForm.secondRevisionId,
      chainForm.inputPartRevisionId,
      chainForm.intermediatePartRevisionId,
      chainForm.outputPartRevisionId,
      chainForm.firstMachineType,
      chainForm.secondMachineType,
      chainForm.firstClampTonnage,
      chainForm.secondClampTonnage,
    ];
    if (
      required.some((value) => !value.trim()) ||
      !/^\d+(?:\.\d+)?$/u.test(chainForm.firstClampTonnage) ||
      !/^\d+(?:\.\d+)?$/u.test(chainForm.secondClampTonnage)
    ) {
      setFormError(t("Complete both exact ordered process steps."));
      return;
    }
    const latestChain =
      chains.kind === "loaded" && chainForm.processChainGlobalId
        ? chains.value.items
            .filter(
              (item) =>
                item.processChainGlobalId === chainForm.processChainGlobalId,
            )
            .sort((left, right) => right.chainVersion - left.chainVersion)[0]
        : undefined;
    if (chainForm.processChainGlobalId && !latestChain) {
      setFormError(t("Select a valid process chain lineage."));
      return;
    }
    const payload: CreateToolingProcessChainRevisionCommand = {
      ...(latestChain
        ? {
            expectedVersion: latestChain.chainVersion,
            processChainGlobalId: latestChain.processChainGlobalId,
          }
        : {}),
      reason: chainForm.reason.trim(),
      steps: [
        {
          clampTonnage: measurement(chainForm.firstClampTonnage, "t"),
          inputPartRevisionGlobalIds: [chainForm.inputPartRevisionId],
          machineType: chainForm.firstMachineType.trim(),
          outputPartRevisionGlobalId: chainForm.intermediatePartRevisionId,
          processKind: "primary_molding",
          stepOrder: 1,
          toolingRevisionGlobalId: chainForm.firstRevisionId,
        },
        {
          clampTonnage: measurement(chainForm.secondClampTonnage, "t"),
          inputPartRevisionGlobalIds: [chainForm.intermediatePartRevisionId],
          machineType: chainForm.secondMachineType.trim(),
          outputPartRevisionGlobalId: chainForm.outputPartRevisionId,
          parentStepOrder: 1,
          processKind: "overmold",
          stepOrder: 2,
          toolingRevisionGlobalId: chainForm.secondRevisionId,
        },
      ],
    };
    runCommand(
      t("Creating ordered Tooling process chain"),
      (context) =>
        dataSource.createToolingProcessChainRevision(
          projectId,
          payload,
          context,
        ),
      (value) => {
        setChains((current) =>
          current.kind === "loaded"
            ? {
                kind: "loaded",
                value: {
                  ...current.value,
                  items: [...current.value.items, value],
                },
              }
            : current,
        );
      },
    );
  };

  if (revisions.kind === "failed") {
    return (
      <Panel
        id="tooling-revision-workspace"
        title={t("Tooling Revision workspace")}
      >
        <RequestFailurePanel failure={revisions.failure} />
        {canRetry(revisions.failure) ? (
          <Button
            onClick={() => {
              setRevisions({ kind: "loading" });
              setChains({ kind: "loading" });
              setAttempt((value) => value + 1);
            }}
          >
            {t("Retry")}
          </Button>
        ) : null}
      </Panel>
    );
  }

  if (revisions.kind === "loading") {
    return (
      <Panel
        id="tooling-revision-workspace"
        title={t("Tooling Revision workspace")}
      >
        <p aria-busy="true" role="status">
          {t("Loading Tooling Revision workspace")}
        </p>
      </Panel>
    );
  }

  const selectedDetail = detail.kind === "loaded" ? detail.value : null;
  const controlledSpecification =
    partSpecification.kind === "loaded"
      ? partSpecification.value.controlledSpecification
      : null;
  const processing = command.kind === "processing";

  return (
    <Panel
      id="tooling-revision-workspace"
      title={t("Tooling Revision workspace")}
    >
      <div className="tooling-set__toolbar">
        <div>
          <SemanticStatus
            label={revisions.value.items.length ? t("Available") : t("Empty")}
            tone={revisions.value.items.length ? "success" : "neutral"}
          />
          <span>
            {t("Immutable Revisions")}:{" "}
            {formatNumber(locale, revisionItems.length)}
          </span>
        </div>
        {revisions.value.permissions.createRevision && sessionCommandContext ? (
          <Button
            disabled={processing || applicability.length === 0}
            onClick={(event) => {
              editorTrigger.current = event.currentTarget;
              setRevisionForm(revisionDraft(applicability));
              setEditor("revision");
              setFormError(null);
            }}
            visual="primary"
          >
            {t("Create Tooling Revision")}
          </Button>
        ) : null}
      </div>

      <div className="tooling-live__workspace">
        <section aria-label={t("Tooling Revision history")}>
          {revisionItems.length ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("Revision")}</th>
                  <th>{t("Reason")}</th>
                  <th>{t("Cavities")}</th>
                  <th>{t("Inserts")}</th>
                </tr>
              </thead>
              <tbody>
                {revisionItems.map((item) => (
                  <tr
                    aria-selected={item.globalId === selectedRevisionId}
                    key={item.globalId}
                  >
                    <td>
                      <button
                        className="table-link"
                        onClick={() => {
                          setDetail({ kind: "loading" });
                          setSelectedRevisionId(item.globalId);
                        }}
                        type="button"
                      >
                        {item.revisionLabel} ·{" "}
                        {formatNumber(locale, item.revisionNumber)}
                      </button>
                    </td>
                    <td data-language-exempt="business-data">{item.reason}</td>
                    <td>{formatNumber(locale, item.cavities.length)}</td>
                    <td>{formatNumber(locale, item.inserts.length)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>{t("No Tooling Revision has been recorded.")}</p>
          )}
        </section>

        <aside aria-label={t("Tooling Revision inspector")}>
          {detail.kind === "loading" ? (
            <p aria-busy="true" role="status">
              {t("Loading exact Tooling Revision")}
            </p>
          ) : detail.kind === "failed" ? (
            <RequestFailurePanel failure={detail.failure} />
          ) : selectedDetail ? (
            <>
              <DefinitionList
                rows={[
                  {
                    label: t("Revision"),
                    value: selectedDetail.revision.revisionLabel,
                    exempt: "business-data",
                  },
                  {
                    label: t("Machine type"),
                    value: selectedDetail.revision.specification.machineType,
                    exempt: "business-data",
                  },
                  {
                    label: t("Tooling type"),
                    value: selectedDetail.revision.specification.toolingType,
                    exempt: "business-data",
                  },
                  {
                    label: t("Snapshot hash"),
                    value: selectedDetail.revision.snapshotHash,
                    exempt: "identifier",
                  },
                ]}
              />
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("Cavity")}</th>
                    <th>{t("Part Revision")}</th>
                    <th>{t("Structure")}</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedDetail.revision.cavities.map((item) => (
                    <tr key={item.globalId}>
                      <td data-language-exempt="business-data">
                        {item.cavityIdentifier}
                      </td>
                      <td data-language-exempt="identifier">
                        {item.partRevisionGlobalId}
                      </td>
                      <td>
                        {item.structuralState === "enabled"
                          ? t("Enabled")
                          : t("Sealed")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {selectedDetail.revision.inserts.length ? (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>{t("Insert")}</th>
                      <th>{t("Version")}</th>
                      <th>{t("Validation")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedDetail.revision.inserts.map((item) => (
                      <tr key={item.globalId}>
                        <td data-language-exempt="business-data">
                          {item.insertCode}
                        </td>
                        <td>{formatNumber(locale, item.insertVersion)}</td>
                        <td>
                          {item.validationState === "validated"
                            ? t("Validated")
                            : t("Not validated")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
              {[
                selectedDetail.lifecycle,
                selectedDetail.supplier,
                selectedDetail.erpLocationAndAsset,
                selectedDetail.combinedTrial,
              ].map((item) => (
                <div
                  className="tooling-live__downstream-row"
                  key={item.reasonCode}
                >
                  <SemanticStatus label={t("Unavailable")} tone="warning" />
                  <span>{unavailableLabel(t, item.reasonCode)}</span>
                </div>
              ))}
            </>
          ) : (
            <p>{t("Select one immutable Revision to inspect it.")}</p>
          )}
        </aside>
      </div>

      <section aria-label={t("Controlled Part specification")}>
        <div className="tooling-set__toolbar">
          <Select
            aria-label={t("Part for controlled specification")}
            data-language-exempt="business-data"
            onChange={(event) => {
              setPartSpecification({ kind: "loading" });
              setSelectedPartId(event.currentTarget.value);
            }}
            value={selectedPartId}
          >
            {parts.map((part) => (
              <option key={part.globalId} value={part.globalId}>
                {part.title} · {part.currentRevision.revisionLabel}
              </option>
            ))}
          </Select>
          {partSpecification.kind === "loaded" &&
          "state" in partSpecification.value.controlledSpecification &&
          partSpecification.value.permissions.createPartSpecification &&
          sessionCommandContext ? (
            <Button
              disabled={processing}
              onClick={(event) => {
                editorTrigger.current = event.currentTarget;
                setPartForm(partSpecificationDraft());
                setEditor("part-specification");
                setFormError(null);
              }}
            >
              {t("Record controlled Part specification")}
            </Button>
          ) : null}
        </div>
        {partSpecification.kind === "loading" ? (
          <p aria-busy="true" role="status">
            {t("Loading controlled Part specification")}
          </p>
        ) : partSpecification.kind === "failed" ? (
          <RequestFailurePanel failure={partSpecification.failure} />
        ) : controlledSpecification && !("state" in controlledSpecification) ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("Kind")}</th>
                <th>{t("Normalized value")}</th>
                <th>{t("Raw source value")}</th>
                <th>{t("Effective from")}</th>
              </tr>
            </thead>
            <tbody>
              {controlledSpecification.items.map((item) => (
                <tr key={item.globalId}>
                  <td>{specificationKindLabel(t, item.kind)}</td>
                  <td data-language-exempt="business-data">
                    {item.normalizedValue}
                  </td>
                  <td data-language-exempt="business-data">{item.rawValue}</td>
                  <td>{item.effectiveFrom}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : controlledSpecification ? (
          <div className="tooling-live__downstream-row">
            <SemanticStatus label={t("Unavailable")} tone="warning" />
            <span>
              {unavailableLabel(t, controlledSpecification.reasonCode)}
            </span>
          </div>
        ) : null}
      </section>

      <section aria-label={t("Tooling process chains")}>
        <div className="tooling-set__toolbar">
          <strong>{t("Tooling process chains")}</strong>
          {chains.kind === "loaded" &&
          chains.value.permissions.createProcessChain &&
          revisionItems.length > 0 &&
          parts.length > 0 &&
          sessionCommandContext ? (
            <Button
              disabled={processing}
              onClick={(event) => {
                editorTrigger.current = event.currentTarget;
                setChainForm(processChainDraft(revisionItems, parts));
                setEditor("process-chain");
                setFormError(null);
              }}
            >
              {t("Create process chain Revision")}
            </Button>
          ) : null}
        </div>
        {chains.kind === "loaded" ? (
          chains.value.items.length ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("Chain")}</th>
                  <th>{t("Version")}</th>
                  <th>{t("Steps")}</th>
                  <th>{t("Reason")}</th>
                </tr>
              </thead>
              <tbody>
                {chains.value.items.map((item) => (
                  <tr key={item.globalId}>
                    <td data-language-exempt="identifier">
                      {item.processChainGlobalId}
                    </td>
                    <td>{formatNumber(locale, item.chainVersion)}</td>
                    <td>{formatNumber(locale, item.steps.length)}</td>
                    <td data-language-exempt="business-data">{item.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>{t("No Tooling process chain has been recorded.")}</p>
          )
        ) : chains.kind === "failed" ? (
          <RequestFailurePanel failure={chains.failure} />
        ) : (
          <p aria-busy="true" role="status">
            {t("Loading Tooling process chains")}
          </p>
        )}
      </section>

      {command.kind === "processing" ? (
        <p aria-live="polite" role="status">
          {command.label}
        </p>
      ) : command.kind === "failed" ? (
        <div>
          <RequestFailurePanel failure={command.failure} />
          {canRetry(command.failure) ? (
            <Button onClick={() => retryCommand.current?.()}>
              {t("Retry")}
            </Button>
          ) : null}
        </div>
      ) : null}

      {editor === "revision" ? (
        <Panel title={t("Create Tooling Revision")}>
          <div className="command-form__grid">
            <LabeledTextInput
              label={t("Revision label")}
              onChange={(event) => {
                setRevisionForm({
                  ...revisionForm,
                  revisionLabel: event.currentTarget.value,
                });
              }}
              value={revisionForm.revisionLabel}
            />
            <LabeledTextInput
              label={t("Reason")}
              onChange={(event) => {
                setRevisionForm({
                  ...revisionForm,
                  reason: event.currentTarget.value,
                });
              }}
              value={revisionForm.reason}
            />
            {(
              [
                ["toolingType", t("Tooling type")],
                ["moldBaseMaterial", t("Mold base material")],
                ["coreMaterial", t("Core material")],
                ["hardness", t("Hardness (HRC)")],
                ["surfaceTreatment", t("Surface treatment")],
                ["cavityCount", t("Cavity count")],
                ["hotRunner", t("Hot runner")],
                ["length", t("Length (mm)")],
                ["width", t("Width (mm)")],
                ["height", t("Height (mm)")],
                ["weight", t("Weight (kg)")],
                ["clampTonnage", t("Clamp tonnage (t)")],
                ["tieBarSpacingX", t("Tie-bar spacing X (mm)")],
                ["tieBarSpacingY", t("Tie-bar spacing Y (mm)")],
                ["injectionCapacity", t("Injection capacity (g)")],
                ["machineType", t("Machine type")],
                ["targetCycle", t("Target cycle (s)")],
                ["targetLife", t("Target life (cycles)")],
                ["warranty", t("Warranty")],
                ["customerStandard", t("Customer standard")],
                ["interfaceRequirement", t("Interface requirement")],
                ["spareParts", t("Spare parts, comma separated")],
                ["deliveryDocuments", t("Delivery documents, comma separated")],
                ["cavityIdentifier", t("Cavity identifier")],
                ["insertCode", t("Optional insert code")],
                ["insertVersion", t("Insert version")],
                ["changeoverDuration", t("Changeover duration (min)")],
                ["validationReason", t("Validation reason")],
                ["externalIdentityValue", t("Optional external identity")],
                ["externalIdentityRawValue", t("Raw external identity")],
                [
                  "externalIdentitySourceObjectId",
                  t("External identity source object"),
                ],
                ["designDocumentRevisionId", t("Design Document Revision")],
                ["designDocumentSnapshotHash", t("Document snapshot hash")],
              ] as const
            ).map(([key, label]) => (
              <LabeledTextInput
                key={key}
                label={label}
                onChange={(event) => {
                  setRevisionForm({
                    ...revisionForm,
                    [key]: event.currentTarget.value,
                  });
                }}
                value={revisionForm[key]}
              />
            ))}
            <Select
              aria-label={t("Tooling applicability")}
              onChange={(event) => {
                setRevisionForm({
                  ...revisionForm,
                  applicabilityId: event.currentTarget.value,
                });
              }}
              value={revisionForm.applicabilityId}
            >
              {applicability.map((item) => (
                <option key={item.globalId} value={item.globalId}>
                  {item.part.revisionLabel} · {item.globalId}
                </option>
              ))}
            </Select>
            <Select
              aria-label={t("Cavity structural state")}
              onChange={(event) => {
                setRevisionForm({
                  ...revisionForm,
                  structuralState: event.currentTarget.value as
                    | "enabled"
                    | "sealed",
                });
              }}
              value={revisionForm.structuralState}
            >
              <option value="enabled">{t("Enabled")}</option>
              <option value="sealed">{t("Sealed")}</option>
            </Select>
            <Select
              aria-label={t("Insert validation state")}
              onChange={(event) => {
                setRevisionForm({
                  ...revisionForm,
                  validationState: event.currentTarget.value as
                    | "not_validated"
                    | "validated",
                });
              }}
              value={revisionForm.validationState}
            >
              <option value="not_validated">{t("Not validated")}</option>
              <option value="validated">{t("Validated")}</option>
            </Select>
          </div>
          {formError ? <p role="alert">{formError}</p> : null}
          <div className="dialog-actions">
            <Button
              disabled={processing}
              onClick={submitRevision}
              visual="primary"
            >
              {t("Create immutable Revision")}
            </Button>
            <Button
              disabled={processing}
              onClick={() => {
                setEditor(null);
              }}
            >
              {t("Cancel")}
            </Button>
          </div>
        </Panel>
      ) : editor === "part-specification" ? (
        <Panel title={t("Record controlled Part specification")}>
          <div className="command-form__grid">
            <Select
              aria-label={t("Controlled specification kind")}
              onChange={(event) => {
                setPartForm({
                  ...partForm,
                  kind: event.currentTarget
                    .value as PartControlledSpecificationKind,
                });
              }}
              value={partForm.kind}
            >
              {(
                [
                  "material_family",
                  "grade",
                  "trademark",
                  "color",
                  "color_masterbatch",
                  "fda_compliance",
                  "regulatory_compliance",
                  "secondary_process",
                ] as const
              ).map((item) => (
                <option key={item} value={item}>
                  {specificationKindLabel(t, item)}
                </option>
              ))}
            </Select>
            <LabeledTextInput
              label={t("Normalized value")}
              onChange={(event) => {
                setPartForm({
                  ...partForm,
                  normalizedValue: event.currentTarget.value,
                });
              }}
              value={partForm.normalizedValue}
            />
            <LabeledTextInput
              label={t("Raw source value")}
              onChange={(event) => {
                setPartForm({
                  ...partForm,
                  rawValue: event.currentTarget.value,
                });
              }}
              value={partForm.rawValue}
            />
            <LabeledTextInput
              label={t("Source object")}
              onChange={(event) => {
                setPartForm({
                  ...partForm,
                  sourceObjectId: event.currentTarget.value,
                });
              }}
              value={partForm.sourceObjectId}
            />
            <LabeledTextInput
              label={t("Effective from")}
              onChange={(event) => {
                setPartForm({
                  ...partForm,
                  effectiveFrom: event.currentTarget.value,
                });
              }}
              type="date"
              value={partForm.effectiveFrom}
            />
            <LabeledTextInput
              label={t("Unit")}
              onChange={(event) => {
                setPartForm({
                  ...partForm,
                  unit: event.currentTarget.value,
                });
              }}
              value={partForm.unit}
            />
          </div>
          {formError ? <p role="alert">{formError}</p> : null}
          <div className="dialog-actions">
            <Button
              disabled={processing}
              onClick={submitPartSpecification}
              visual="primary"
            >
              {t("Record immutable specification")}
            </Button>
            <Button
              disabled={processing}
              onClick={() => {
                setEditor(null);
              }}
            >
              {t("Cancel")}
            </Button>
          </div>
        </Panel>
      ) : editor === "process-chain" ? (
        <Panel title={t("Create process chain Revision")}>
          <label>
            <span>{t("Process chain lineage")}</span>
            <Select
              onChange={(event) => {
                setChainForm({
                  ...chainForm,
                  processChainGlobalId: event.currentTarget.value,
                });
              }}
              value={chainForm.processChainGlobalId}
            >
              <option value="">{t("New process chain")}</option>
              {chains.kind === "loaded"
                ? Array.from(
                    new Map(
                      [...chains.value.items]
                        .sort(
                          (left, right) =>
                            right.chainVersion - left.chainVersion,
                        )
                        .map((item) => [item.processChainGlobalId, item]),
                    ).values(),
                  ).map((item) => (
                    <option
                      key={item.processChainGlobalId}
                      value={item.processChainGlobalId}
                    >
                      {item.processChainGlobalId} · {t("Version")}{" "}
                      {formatNumber(locale, item.chainVersion)}
                    </option>
                  ))
                : null}
            </Select>
          </label>
          <LabeledTextInput
            label={t("Reason")}
            onChange={(event) => {
              setChainForm({
                ...chainForm,
                reason: event.currentTarget.value,
              });
            }}
            value={chainForm.reason}
          />
          {([1, 2] as const).map((step) => {
            const revisionKey =
              step === 1 ? "firstRevisionId" : "secondRevisionId";
            const machineKey =
              step === 1 ? "firstMachineType" : "secondMachineType";
            const tonnageKey =
              step === 1 ? "firstClampTonnage" : "secondClampTonnage";
            return (
              <fieldset key={step}>
                <legend>
                  {t("Process step")} {formatNumber(locale, step)}
                </legend>
                <Select
                  aria-label={
                    step === 1
                      ? t("First step Tooling Revision")
                      : t("Second step Tooling Revision")
                  }
                  onChange={(event) => {
                    setChainForm({
                      ...chainForm,
                      [revisionKey]: event.currentTarget.value,
                    });
                  }}
                  value={chainForm[revisionKey]}
                >
                  {revisionItems.map((item) => (
                    <option key={item.globalId} value={item.globalId}>
                      {item.revisionLabel}
                    </option>
                  ))}
                </Select>
                <LabeledTextInput
                  label={t("Machine type")}
                  onChange={(event) => {
                    setChainForm({
                      ...chainForm,
                      [machineKey]: event.currentTarget.value,
                    });
                  }}
                  value={chainForm[machineKey]}
                />
                <LabeledTextInput
                  label={t("Clamp tonnage (t)")}
                  onChange={(event) => {
                    setChainForm({
                      ...chainForm,
                      [tonnageKey]: event.currentTarget.value,
                    });
                  }}
                  value={chainForm[tonnageKey]}
                />
              </fieldset>
            );
          })}
          {(
            [
              ["inputPartRevisionId", t("Input Part Revision")],
              ["intermediatePartRevisionId", t("Intermediate Part Revision")],
              ["outputPartRevisionId", t("Output Part Revision")],
            ] as const
          ).map(([key, label]) => (
            <Select
              aria-label={label}
              data-language-exempt="business-data"
              key={key}
              onChange={(event) => {
                setChainForm({
                  ...chainForm,
                  [key]: event.currentTarget.value,
                });
              }}
              value={chainForm[key]}
            >
              {parts.map((item) => (
                <option
                  key={item.currentRevision.globalId}
                  value={item.currentRevision.globalId}
                >
                  {item.title} · {item.currentRevision.revisionLabel}
                </option>
              ))}
            </Select>
          ))}
          {formError ? <p role="alert">{formError}</p> : null}
          <div className="dialog-actions">
            <Button
              disabled={processing}
              onClick={submitProcessChain}
              visual="primary"
            >
              {t("Create immutable process chain")}
            </Button>
            <Button
              disabled={processing}
              onClick={() => {
                setEditor(null);
              }}
            >
              {t("Cancel")}
            </Button>
          </div>
        </Panel>
      ) : null}
    </Panel>
  );
}
