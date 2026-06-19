// Tipos que reflejan las tablas del schema, acotados a lo que la UI usa hoy.
// (Las vistas derivadas viven en data/*.ts; otras tablas se tipan al usarlas.)
export type ResolutionStatus = "resolved" | "unresolved" | "ambiguous";
export type ChannelCampaignStatus = "pending" | "verified" | "incomplete" | "failed";
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
