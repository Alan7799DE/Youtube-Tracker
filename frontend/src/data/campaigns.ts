import type { SupabaseClient } from "@supabase/supabase-js";
import type { Campaign } from "../lib/types";
import { briefToRequirements, type CampaignForm } from "../lib/brief";

export async function listCampaigns(client: SupabaseClient): Promise<Campaign[]> {
  const { data, error } = await client
    .from("campaigns")
    .select("*")
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as Campaign[];
}

// Crea la campaña + sus requirements (del brief manual) + asignaciones de canales,
// todo por RLS. Devuelve el id de la campaña.
export async function createCampaign(
  client: SupabaseClient,
  form: CampaignForm,
  channelIds: string[]
): Promise<string> {
  const { data, error } = await client
    .from("campaigns")
    .insert({ brand: form.brand, name: form.name, ends_at: form.endsAt, status: "active" })
    .select("id")
    .single();
  if (error) throw error;
  const campaignId = (data as { id: string }).id;

  const reqs = briefToRequirements(form).map((r) => ({ ...r, campaign_id: campaignId }));
  if (reqs.length > 0) {
    const { error: e2 } = await client.from("requirements").insert(reqs);
    if (e2) throw e2;
  }

  if (channelIds.length > 0) {
    const rows = channelIds.map((channel_id) => ({ campaign_id: campaignId, channel_id, status: "pending" }));
    const { error: e3 } = await client.from("campaign_channels").insert(rows);
    if (e3) throw e3;
  }

  return campaignId;
}

export async function closeCampaign(client: SupabaseClient, id: string): Promise<void> {
  const { error } = await client.from("campaigns").update({ status: "closed" }).eq("id", id);
  if (error) throw error;
}
