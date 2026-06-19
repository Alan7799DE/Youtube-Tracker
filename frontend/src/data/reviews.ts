import type { SupabaseClient } from "@supabase/supabase-js";

export interface ReviewItem {
  verificationId: string;
  videoId: string;
  youtubeVideoId: string;
  title: string | null;
  campaignName: string;
}

export async function listReviewQueue(client: SupabaseClient): Promise<ReviewItem[]> {
  const { data, error } = await client
    .from("verifications")
    .select("id, overall_status, campaigns(name), video_submissions(id, youtube_video_id, title)")
    .eq("overall_status", "review");
  if (error) throw error;
  return (data ?? []).map((v: any) => ({
    verificationId: v.id,
    videoId: v.video_submissions?.id ?? "",
    youtubeVideoId: v.video_submissions?.youtube_video_id ?? "",
    title: v.video_submissions?.title ?? null,
    campaignName: v.campaigns?.name ?? "",
  }));
}

export interface ReviewDecision {
  verificationId: string;
  reviewerId: string;
  pass: boolean;
  confirmedGameplay: boolean;
}

// La persona decide; queda registrado con reviewer_id = el usuario actual (RLS).
export async function insertReview(client: SupabaseClient, d: ReviewDecision): Promise<void> {
  const { error } = await client.from("reviews").insert({
    verification_id: d.verificationId,
    reviewer_id: d.reviewerId,
    decision: d.pass ? "pass" : "fail",
    confirmed_gameplay: d.confirmedGameplay,
  });
  if (error) throw error;
}
