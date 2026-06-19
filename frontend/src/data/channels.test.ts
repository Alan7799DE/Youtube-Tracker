import { describe, it, expect, vi } from "vitest";
import { listChannels, applyReconcilePlan } from "./channels";
import type { ReconcilePlan } from "../lib/reconcile";

describe("listChannels", () => {
  it("trae los canales activos de la org via RLS", async () => {
    const order = vi.fn().mockResolvedValue({ data: [{ id: "c1", source_url: "https://youtube.com/@a" }], error: null });
    const eq = vi.fn().mockReturnValue({ order });
    const select = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ select });
    const client = { from } as any;

    const rows = await listChannels(client);
    expect(from).toHaveBeenCalledWith("channels");
    expect(eq).toHaveBeenCalledWith("is_active", true);
    expect(rows[0].id).toBe("c1");
  });
});

describe("applyReconcilePlan", () => {
  it("inserta los nuevos como unresolved y (des)activa en lote según el plan", async () => {
    const insert = vi.fn().mockResolvedValue({ error: null });
    const inFn = vi.fn().mockResolvedValue({ error: null });
    const update = vi.fn().mockReturnValue({ in: inFn });
    const from = vi.fn().mockReturnValue({ insert, update });
    const client = { from } as any;

    const plan: ReconcilePlan = {
      toAdd: ["https://youtube.com/@c"],
      toKeep: [],
      toReactivate: [{ id: "4", source_url: "https://youtube.com/@d", is_active: false }],
      toDeactivate: [{ id: "2", source_url: "https://youtube.com/@b", is_active: true }],
    };
    await applyReconcilePlan(client, plan);

    expect(insert).toHaveBeenCalledWith([
      { source_url: "https://youtube.com/@c", resolution_status: "unresolved", is_active: true },
    ]);
    expect(update).toHaveBeenCalledWith({ is_active: true });
    expect(update).toHaveBeenCalledWith({ is_active: false });
    expect(inFn).toHaveBeenCalledWith("id", ["4"]);
    expect(inFn).toHaveBeenCalledWith("id", ["2"]);
  });
});
