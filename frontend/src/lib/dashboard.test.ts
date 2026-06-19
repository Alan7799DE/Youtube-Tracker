import { describe, it, expect } from "vitest";
import { summarize, type DashboardRow } from "./dashboard";

function row(status: DashboardRow["status"], hasVideoInReview = false): DashboardRow {
  return { id: Math.random().toString(), campaignName: "c", channelName: "ch", status, hasVideoInReview, lastVideoId: null };
}

describe("summarize", () => {
  it("cuenta total, al día, atención y pendientes", () => {
    const rows = [
      row("verified"),
      row("incomplete"),
      row("failed"),
      row("pending", true), // en revisión -> atención
      row("pending", false), // pendiente puro
      row("pending", false),
    ];
    expect(summarize(rows)).toEqual({ total: 6, onTrack: 1, attention: 3, pending: 2 });
  });

  it("lista vacía da todo en cero", () => {
    expect(summarize([])).toEqual({ total: 0, onTrack: 0, attention: 0, pending: 0 });
  });
});
