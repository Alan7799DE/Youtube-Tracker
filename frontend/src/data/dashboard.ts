import type { SupabaseClient } from "@supabase/supabase-js";
import type { DashboardRow } from "../lib/dashboard";

// Trae las filas canal-campaña con el nombre de su campaña y canal (por RLS solo
// las de la org del usuario). `hasVideoInReview`/`lastVideoId` se derivan del
// último video; se dejan en su valor base hasta cablear ese join.
export async function listDashboardRows(client: SupabaseClient): Promise<DashboardRow[]> {
  const { data, error } = await client
    .from("campaign_channels")
    .select("id, status, campaigns(name), channels(name)");
  if (error) throw error;
  return (data ?? []).map((r: any) => ({
    id: r.id,
    campaignName: r.campaigns?.name ?? "",
    channelName: r.channels?.name ?? "",
    status: r.status,
    hasVideoInReview: r.has_video_in_review ?? false,
    lastVideoId: r.last_video_id ?? null,
  }));
}
