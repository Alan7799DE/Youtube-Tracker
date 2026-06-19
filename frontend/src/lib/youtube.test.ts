import { describe, it, expect } from "vitest";
import { youtubeTimestampUrl } from "./youtube";

describe("youtubeTimestampUrl", () => {
  it("agrega el timestamp cuando hay segundos", () => {
    expect(youtubeTimestampUrl("VID123", 42)).toBe("https://youtu.be/VID123?t=42");
  });
  it("sin segundos devuelve el link base", () => {
    expect(youtubeTimestampUrl("VID123", null)).toBe("https://youtu.be/VID123");
    expect(youtubeTimestampUrl("VID123", 0)).toBe("https://youtu.be/VID123");
  });
});
