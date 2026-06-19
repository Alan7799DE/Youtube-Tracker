export type ResolutionStatus = "resolved" | "unresolved" | "ambiguous";
export type ChannelCampaignStatus = "pending" | "verified" | "incomplete" | "failed";
export type VideoStatus = "detected" | "awaiting_transcript" | "verifying" | "resolved" | "needs_human" | "error";
export type OverallStatus = "pass" | "fail" | "review";
export type RequirementType = "link_in_desc" | "code_in_desc" | "mention_name" | "describe_game" | "show_gameplay";

export interface Channel {
  id: string;
  source_url: string;
  handle: string | null;
  name: string | null;
  youtube_channel_id: string | null;
  resolution_status: ResolutionStatus;
  is_active: boolean;
}

export interface Campaign {
  id: string;
  brand: string;
  name: string;
  status: "active" | "closed";
  starts_at: string | null;
  ends_at: string;
}

export interface Requirement {
  id: string;
  campaign_id: string;
  code: string;
  type: RequirementType;
  spec: Record<string, unknown>;
  method: "deterministic" | "llm" | "human";
  required: boolean;
}

export interface CampaignChannel {
  id: string;
  campaign_id: string;
  channel_id: string;
  status: ChannelCampaignStatus;
}

export interface VideoSubmission {
  id: string;
  channel_id: string;
  youtube_video_id: string;
  title: string | null;
  url: string | null;
  status: VideoStatus;
}

export interface Verification {
  id: string;
  video_id: string;
  campaign_id: string;
  overall_status: OverallStatus;
}

export interface RequirementResult {
  id: string;
  verification_id: string;
  requirement_id: string;
  met: boolean;
  confidence: number | null;
  evidence: string | null;
  evidence_timestamp_s: number | null;
}
