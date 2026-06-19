import { describe, it, expect } from "vitest";
import { toMessage } from "./errors";

describe("toMessage", () => {
  it("usa .message de un Error", () => {
    expect(toMessage(new Error("falló"))).toBe("falló");
  });
  it("usa .message de un objeto tipo error de Supabase", () => {
    expect(toMessage({ message: "RLS denied", code: "42501" })).toBe("RLS denied");
  });
  it("hace fallback a String para valores planos", () => {
    expect(toMessage("texto")).toBe("texto");
  });
});
