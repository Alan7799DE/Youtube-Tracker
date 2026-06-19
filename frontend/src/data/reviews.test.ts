import { describe, it, expect, vi } from "vitest";
import { insertReview, listReviewQueue } from "./reviews";

describe("listReviewQueue", () => {
  it("trae solo verificaciones en review y aplana video/campaña", async () => {
    const eq = vi.fn().mockResolvedValue({
      data: [{ id: "ver1", overall_status: "review", campaigns: { name: "Camp" }, video_submissions: { id: "v1", youtube_video_id: "YT1", title: "t" } }],
      error: null,
    });
    const select = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ select });
    const client = { from } as any;

    const items = await listReviewQueue(client);
    expect(from).toHaveBeenCalledWith("verifications");
    expect(eq).toHaveBeenCalledWith("overall_status", "review");
    expect(items[0]).toEqual({ verificationId: "ver1", videoId: "v1", youtubeVideoId: "YT1", title: "t", campaignName: "Camp" });
  });
});

describe("insertReview", () => {
  it("inserta la decisión con el reviewer_id del usuario", async () => {
    const insert = vi.fn().mockResolvedValue({ error: null });
    const from = vi.fn().mockReturnValue({ insert });
    const client = { from } as any;

    await insertReview(client, { verificationId: "ver1", reviewerId: "u1", pass: true, confirmedGameplay: true });
    expect(from).toHaveBeenCalledWith("reviews");
    expect(insert).toHaveBeenCalledWith({
      verification_id: "ver1",
      reviewer_id: "u1",
      decision: "pass",
      confirmed_gameplay: true,
    });
  });
});
