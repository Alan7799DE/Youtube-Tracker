import { describe, it, expect } from "vitest";
import { parseChannelsFile } from "./parseChannels";

describe("parseChannelsFile", () => {
  it("toma la primera columna y saltea el header y las filas vacías", () => {
    const csv = "url\nhttps://youtube.com/@a\n\nhttps://youtube.com/@b\n";
    const buf = new TextEncoder().encode(csv).buffer;
    expect(parseChannelsFile(buf)).toEqual(["https://youtube.com/@a", "https://youtube.com/@b"]);
  });
});
