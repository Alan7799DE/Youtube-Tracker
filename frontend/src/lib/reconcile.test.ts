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

  it("archivo vacío -> desactiva todos los activos", () => {
    const existing = [
      { id: "1", source_url: "https://youtube.com/@a", is_active: true },
      { id: "2", source_url: "https://youtube.com/@b", is_active: false },
    ];
    const plan = reconcile([], existing);
    expect(plan.toAdd).toEqual([]);
    expect(plan.toDeactivate.map((c) => c.id)).toEqual(["1"]);
    expect(plan.toReactivate).toEqual([]);
    expect(plan.toKeep).toEqual([]);
  });

  it("sin canales previos -> todos van a agregar", () => {
    const plan = reconcile(["https://youtube.com/@a", "https://youtube.com/@b"], []);
    expect(plan.toAdd).toEqual(["https://youtube.com/@a", "https://youtube.com/@b"]);
  });

  it("deduplica URLs repetidas en el archivo (normalizando)", () => {
    const plan = reconcile(["https://youtube.com/@a", "https://YouTube.com/@a/", "https://youtube.com/@a"], []);
    expect(plan.toAdd).toEqual(["https://youtube.com/@a"]);
  });
});
