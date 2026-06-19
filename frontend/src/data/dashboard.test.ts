import { describe, it, expect, vi } from "vitest";
import { listDashboardRows } from "./dashboard";

describe("listDashboardRows", () => {
  it("lee campaign_channels y aplana los nombres de campaña/canal", async () => {
    const select = vi.fn().mockResolvedValue({
      data: [{ id: "cc1", status: "verified", campaigns: { name: "Camp" }, channels: { name: "Canal" } }],
      error: null,
    });
    const from = vi.fn().mockReturnValue({ select });
    const client = { from } as any;

    const rows = await listDashboardRows(client);
    expect(from).toHaveBeenCalledWith("campaign_channels");
    expect(rows[0]).toEqual({
      id: "cc1",
      campaignName: "Camp",
      channelName: "Canal",
      status: "verified",
      hasVideoInReview: false,
      lastVideoId: null,
    });
  });
});
