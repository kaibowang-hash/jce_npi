export function parseCsv(content: string, sourceName: string): string[][];
export function catalogFromRows(
  rows: string[][],
  sourceName: string,
): Map<string, string>;
