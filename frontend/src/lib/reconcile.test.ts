import { describe, it, expect } from "vitest";
import { reconcile } from "./reconcile";

describe("reconcile", () => {
  it("agrega, mantiene, desactiva y reactiva (case/slash-insensitive)", () => {
    const newUrls = ["https://YouTube.com/@A/", "https://youtube.com/@c", "https://youtube.com/@d"];
    const existing = [
      { id: "1", source_url: "https://youtube.com/@a", is_active: true },
      { id: "2", source_url: "https://youtube.com/@b", is_active: true },
      { id: "4", source_url: "https://youtube.com/@d", is_active: false },
    ];
    const plan = reconcile(newUrls, existing);
    expect(plan.toAdd).toEqual(["https://youtube.com/@c"]);
    expect(plan.toKeep.map((c) => c.id)).toEqual(["1"]);
    expect(plan.toDeactivate.map((c) => c.id)).toEqual(["2"]);
    expect(plan.toReactivate.map((c) => c.id)).toEqual(["4"]);
  });
});
