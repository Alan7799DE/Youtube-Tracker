import { describe, it, expect } from "vitest";
import * as XLSX from "xlsx";
import { parseChannelsFile } from "./parseChannels";

describe("parseChannelsFile", () => {
  it("toma la primera columna y saltea el header y las filas vacías", () => {
    const csv = "url\nhttps://youtube.com/@a\n\nhttps://youtube.com/@b\n";
    const buf = new TextEncoder().encode(csv).buffer;
    expect(parseChannelsFile(buf)).toEqual(["https://youtube.com/@a", "https://youtube.com/@b"]);
  });

  it("no saltea la primera fila si no es un header conocido (es una URL)", () => {
    const csv = "https://youtube.com/@a\nhttps://youtube.com/@b\n";
    const buf = new TextEncoder().encode(csv).buffer;
    expect(parseChannelsFile(buf)).toEqual(["https://youtube.com/@a", "https://youtube.com/@b"]);
  });

  it("recorta espacios alrededor de cada valor", () => {
    const csv = "url\n  https://youtube.com/@a  \n";
    const buf = new TextEncoder().encode(csv).buffer;
    expect(parseChannelsFile(buf)).toEqual(["https://youtube.com/@a"]);
  });

  it("lee un .xlsx real tomando la primera columna", () => {
    const ws = XLSX.utils.aoa_to_sheet([["url"], ["https://youtube.com/@x"], ["https://youtube.com/@y"]]);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Hoja1");
    const buf = XLSX.write(wb, { type: "array", bookType: "xlsx" }) as ArrayBuffer;
    expect(parseChannelsFile(buf)).toEqual(["https://youtube.com/@x", "https://youtube.com/@y"]);
  });

  it("archivo vacío -> lista vacía", () => {
    const buf = new TextEncoder().encode("").buffer;
    expect(parseChannelsFile(buf)).toEqual([]);
  });
});
