import {
  isErpProjectionToolAssetValues,
  LiveErpProjectionsDataSource,
  type ErpProjectionCollectionViewModel,
  type ErpProjectionItemViewModel,
  type ErpProjectionToolAssetValues,
  type ErpProjectionsDataSource,
} from "./erp-projections-data-source";

export interface ConfirmedToolAssetProjection {
  item: ErpProjectionItemViewModel;
  values: ErpProjectionToolAssetValues;
}

export interface ToolingAcceptanceAssetDataSource {
  loadAssetProjections(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ErpProjectionCollectionViewModel>;
}

export function confirmedToolAssetProjection(
  item: ErpProjectionItemViewModel,
): ConfirmedToolAssetProjection | null {
  const truth = item.currentTruth;
  if (
    item.projectionKind !== "tool_asset_status" ||
    item.scopeKind !== "tooling_set" ||
    item.availability !== "available" ||
    item.freshness !== "fresh" ||
    item.disposition !== "applied_current" ||
    truth?.observationGlobalId !== item.observationGlobalId ||
    truth.sourceVersion !== item.sourceVersion ||
    truth.sourceModifiedAt !== item.sourceModifiedAt ||
    truth.receivedAt !== item.receivedAt ||
    truth.payloadHash !== item.payloadHash ||
    !isErpProjectionToolAssetValues(truth.values) ||
    truth.values.toolingSetGlobalId !== item.scopeGlobalId
  ) {
    return null;
  }
  return { item, values: truth.values };
}

export class LiveToolingAcceptanceAssetDataSource implements ToolingAcceptanceAssetDataSource {
  constructor(
    private readonly erpProjections: ErpProjectionsDataSource = new LiveErpProjectionsDataSource(),
  ) {}

  async loadAssetProjections(
    projectId: string,
    signal: AbortSignal,
  ): Promise<ErpProjectionCollectionViewModel> {
    return await this.erpProjections.loadProjectProjections(
      projectId,
      signal,
      "tool_asset_status",
    );
  }
}
