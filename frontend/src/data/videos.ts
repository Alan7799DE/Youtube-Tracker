import type { SupabaseClient } from "@supabase/supabase-js";
import type { OverallStatus } from "../lib/types";

export interface ResultView {
  code: string;
  met: boolean;
  confidence: number | null;
  evidence: string | null;
  evidenceTimestampS: number | null;
}

export interface CampaignVerdict {
  campaignName: string;
  overallStatus: OverallStatus;
  results: ResultView[];
}

export interface VideoDetail {
  id: string;
  title: string | null;
  youtubeVideoId: string;
  verdicts: CampaignVerdict[];
}

// Trae el video con sus verificaciones por campaña y los resultados por requisito.
export async function getVideoDetail(client: SupabaseClient, id: string): Promise<VideoDetail> {
  const { data, error } = await client
    .from("video_submissions")
    .select(
      "id, title, youtube_video_id, verifications(overall_status, campaigns(name), requirement_results(met, confidence, evidence, evidence_timestamp_s, requirements(code)))"
    )
    .eq("id", id)
    .single();
  if (error) throw error;
  const v = data as any;
  return {
    id: v.id,
    title: v.title ?? null,
    youtubeVideoId: v.youtube_video_id,
    verdicts: (v.verifications ?? []).map((ver: any) => ({
      campaignName: ver.campaigns?.name ?? "",
      overallStatus: ver.overall_status as OverallStatus,
      results: (ver.requirement_results ?? []).map((r: any) => ({
        code: r.requirements?.code ?? "",
        met: r.met,
        confidence: r.confidence ?? null,
        evidence: r.evidence ?? null,
        evidenceTimestampS: r.evidence_timestamp_s ?? null,
      })),
    })),
  };
}
