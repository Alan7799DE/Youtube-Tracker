import { describe, it, expect, vi } from "vitest";
import { createCampaign, closeCampaign } from "./campaigns";
import type { CampaignForm } from "../lib/brief";

const form: CampaignForm = {
  brand: "Acme",
  name: "Lanzamiento",
  endsAt: "2026-07-01",
  gameName: "MiJuego",
  expectedLink: "https://dl.game/x",
  code: "GAMER20",
  requirements: { R1: true, R2: false, R3: false, R4: false, R5: false },
};

describe("createCampaign", () => {
  it("inserta campaña, requirements y asignaciones por RLS", async () => {
    const single = vi.fn().mockResolvedValue({ data: { id: "camp1" }, error: null });
    const select = vi.fn().mockReturnValue({ single });
    const insertCampaign = vi.fn().mockReturnValue({ select });
    const insertReqs = vi.fn().mockResolvedValue({ error: null });
    const insertCC = vi.fn().mockResolvedValue({ error: null });
    const from = vi.fn((table: string) => {
      if (table === "campaigns") return { insert: insertCampaign };
      if (table === "requirements") return { insert: insertReqs };
      if (table === "campaign_channels") return { insert: insertCC };
      throw new Error("tabla inesperada " + table);
    });
    const client = { from } as any;

    const id = await createCampaign(client, form, ["ch1", "ch2"]);
    expect(id).toBe("camp1");
    expect(insertCampaign).toHaveBeenCalledWith({ brand: "Acme", name: "Lanzamiento", ends_at: "2026-07-01", status: "active" });
    expect(insertReqs).toHaveBeenCalledWith([
      { code: "R1", type: "link_in_desc", spec: { expected_link: "https://dl.game/x" }, method: "deterministic", required: true, campaign_id: "camp1" },
    ]);
    expect(insertCC).toHaveBeenCalledWith([
      { campaign_id: "camp1", channel_id: "ch1", status: "pending" },
      { campaign_id: "camp1", channel_id: "ch2", status: "pending" },
    ]);
  });
});

describe("closeCampaign", () => {
  it("marca la campaña como closed (no borra)", async () => {
    const eq = vi.fn().mockResolvedValue({ error: null });
    const update = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ update });
    const client = { from } as any;
    await closeCampaign(client, "camp1");
    expect(update).toHaveBeenCalledWith({ status: "closed" });
    expect(eq).toHaveBeenCalledWith("id", "camp1");
  });
});
