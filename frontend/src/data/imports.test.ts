import { describe, it, expect, vi } from "vitest";
import { listImportRuns } from "./imports";

describe("listImportRuns", () => {
  it("trae las últimas corridas ordenadas por fecha desc", async () => {
    const limit = vi.fn().mockResolvedValue({ data: [{ id: "r1" }], error: null });
    const order = vi.fn().mockReturnValue({ limit });
    const select = vi.fn().mockReturnValue({ order });
    const from = vi.fn().mockReturnValue({ select });
    const client = { from } as any;

    const rows = await listImportRuns(client);
    expect(from).toHaveBeenCalledWith("import_runs");
    expect(order).toHaveBeenCalledWith("created_at", { ascending: false });
    expect(rows[0].id).toBe("r1");
  });
});
