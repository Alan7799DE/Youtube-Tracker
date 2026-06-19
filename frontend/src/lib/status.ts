import type { ChannelCampaignStatus } from "./types";

export type Tone = "success" | "warning" | "danger" | "neutral" | "info";
export interface Badge { label: string; tone: Tone; }

const MAP: Record<ChannelCampaignStatus, Badge> = {
  verified: { label: "Compliant", tone: "success" },
  incomplete: { label: "Incomplete", tone: "warning" },
  failed: { label: "Not met", tone: "danger" },
  pending: { label: "Pending", tone: "neutral" },
};

export function channelStatusBadge(status: ChannelCampaignStatus): Badge {
  return MAP[status];
}

export const REVIEW_BADGE: Badge = { label: "In review", tone: "info" };

// El dashboard muestra 5 estados: si el canal-campaña sigue 'pending' pero tiene
// un video esperando revisión humana, se muestra "In review" (derivado del video).
export function dashboardRowBadge(status: ChannelCampaignStatus, hasVideoInReview: boolean): Badge {
  if (status === "pending" && hasVideoInReview) return REVIEW_BADGE;
  return channelStatusBadge(status);
}
