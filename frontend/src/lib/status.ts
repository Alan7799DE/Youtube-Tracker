import type { ChannelCampaignStatus } from "./types";

export type Tone = "success" | "warning" | "danger" | "neutral" | "info";
export interface Badge { label: string; tone: Tone; }

const MAP: Record<ChannelCampaignStatus, Badge> = {
  verified: { label: "Cumple", tone: "success" },
  incomplete: { label: "Incompleto", tone: "warning" },
  failed: { label: "No cumplió", tone: "danger" },
  pending: { label: "Pendiente", tone: "neutral" },
};

export function channelStatusBadge(status: ChannelCampaignStatus): Badge {
  return MAP[status];
}

export const REVIEW_BADGE: Badge = { label: "En revisión", tone: "info" };

// El dashboard muestra 5 estados: si el canal-campaña sigue 'pending' pero tiene
// un video esperando revisión humana, se muestra "En revisión" (derivado del video).
export function dashboardRowBadge(status: ChannelCampaignStatus, hasVideoInReview: boolean): Badge {
  if (status === "pending" && hasVideoInReview) return REVIEW_BADGE;
  return channelStatusBadge(status);
}
