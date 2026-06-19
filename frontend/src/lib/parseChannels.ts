import * as XLSX from "xlsx";

const HEADER = new Set(["url", "urls", "canal", "canales", "channel", "channels", "link", "links"]);

// Lee CSV o .xlsx (SheetJS autodetecta) y devuelve la primera columna, sin header ni vacíos.
export function parseChannelsFile(data: ArrayBuffer): string[] {
  const wb = XLSX.read(data, { type: "array" });
  const sheet = wb.Sheets[wb.SheetNames[0]];
  const rows = XLSX.utils.sheet_to_json<string[]>(sheet, { header: 1, blankrows: false });
  const out: string[] = [];
  rows.forEach((row, i) => {
    const v = String(row?.[0] ?? "").trim();
    if (!v) return;
    if (i === 0 && HEADER.has(v.toLowerCase())) return;
    out.push(v);
  });
  return out;
}
