import type {
  ERPMasterKind,
  ERPMasterPage,
  ERPMasterRecord,
} from "../../src/api/erp-master-data-source";

export function masterPage(
  kind: ERPMasterKind,
  options: Partial<ERPMasterPage> = {},
): ERPMasterPage {
  const modified = "2026-09-06T02:00:00Z";
  const common = { enabled: true, sourceModifiedAt: modified };
  const items: ERPMasterRecord[] =
    kind === "machine"
      ? [
          {
            ...common,
            sourceKey: "IM-550-02",
            displayName: "Injection machine 550T",
            groupKey: null,
          },
        ]
      : kind === "item"
        ? [
            {
              ...common,
              sourceKey: "MAT-PA66-GF30",
              displayName: "PA66-GF30 natural",
              groupKey: "Materials",
              stockUom: "kg",
              isStockItem: true,
            },
          ]
        : kind === "item_group"
          ? [
              {
                ...common,
                sourceKey: "Materials",
                displayName: "Materials",
                parentKey: null,
                isGroup: false,
              },
            ]
          : [
              {
                ...common,
                sourceKey: "SYNTHETIC-CUSTOMER",
                displayName: "Synthetic customer",
                groupKey: null,
              },
            ];
  return {
    schemaVersion: 1,
    catalogKind: kind,
    sourceVersion: 1,
    sourceModifiedAt: modified,
    lastSynchronizedAt: new Date().toISOString().replace(/\.\d{3}Z$/u, "Z"),
    total: items.length,
    offset: 0,
    limit: 20,
    items,
    ...options,
  };
}
