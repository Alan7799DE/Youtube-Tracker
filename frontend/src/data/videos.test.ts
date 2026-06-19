import { describe, it, expect, vi } from "vitest";
import { getVideoDetail } from "./videos";

describe("getVideoDetail", () => {
  it("aplana verificaciones y resultados por campaña", async () => {
    const single = vi.fn().mockResolvedValue({
      data: {
        id: "v1",
        title: "Mi video",
        youtube_video_id: "YT1",
        verifications: [
          {
            overall_status: "pass",
            campaigns: { name: "Camp" },
            requirement_results: [
              { met: true, confidence: 0.9, evidence: "link", evidence_timestamp_s: 30, requirements: { code: "R1" } },
            ],
          },
        ],
      },
      error: null,
    });
    const eq = vi.fn().mockReturnValue({ single });
    const select = vi.fn().mockReturnValue({ eq });
    const from = vi.fn().mockReturnValue({ select });
    const client = { from } as any;

    const detail = await getVideoDetail(client, "v1");
    expect(from).toHaveBeenCalledWith("video_submissions");
    expect(detail.youtubeVideoId).toBe("YT1");
    expect(detail.verdicts[0].campaignName).toBe("Camp");
    expect(detail.verdicts[0].results[0]).toEqual({
      code: "R1", met: true, confidence: 0.9, evidence: "link", evidenceTimestampS: 30,
    });
  });
});
