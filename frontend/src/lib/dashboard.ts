import type { ChannelCampaignStatus } from "./types";

export interface DashboardRow {
  id: string;
  campaignName: string;
  channelName: string;
  status: ChannelCampaignStatus;
  hasVideoInReview: boolean;
  lastVideoId: string | null;
}

export interface DashboardSummary {
  total: number;
  onTrack: number;   // verified
  attention: number; // incomplete | failed | (pending con video en revisión)
  pending: number;   // pending sin video en revisión
}

export function summarize(rows: DashboardRow[]): DashboardSummary {
  const s: DashboardSummary = { total: rows.length, onTrack: 0, attention: 0, pending: 0 };
  for (const r of rows) {
    if (r.status === "verified") s.onTrack++;
    else if (r.status === "incomplete" || r.status === "failed") s.attention++;
    else if (r.status === "pending" && r.hasVideoInReview) s.attention++;
    else s.pending++; // pending sin revisión
  }
  return s;
}
