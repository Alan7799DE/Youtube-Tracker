import type { SupabaseClient } from "@supabase/supabase-js";
import type { Channel } from "../lib/types";
import type { ReconcilePlan } from "../lib/reconcile";

export async function listChannels(client: SupabaseClient): Promise<Channel[]> {
  const { data, error } = await client
    .from("channels")
    .select("*")
    .eq("is_active", true)
    .order("created_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as Channel[];
}

// Aplica un plan de reconciliación por RLS: inserta los nuevos como `unresolved`,
// reactiva los que volvieron y desactiva los que ya no están (soft-delete).
export async function applyReconcilePlan(client: SupabaseClient, plan: ReconcilePlan): Promise<void> {
  if (plan.toAdd.length > 0) {
    const rows = plan.toAdd.map((source_url) => ({
      source_url,
      resolution_status: "unresolved" as const,
      is_active: true,
    }));
    const { error } = await client.from("channels").insert(rows);
    if (error) throw error;
  }
  if (plan.toReactivate.length > 0) {
    const { error } = await client
      .from("channels")
      .update({ is_active: true })
      .in("id", plan.toReactivate.map((c) => c.id));
    if (error) throw error;
  }
  if (plan.toDeactivate.length > 0) {
    const { error } = await client
      .from("channels")
      .update({ is_active: false })
      .in("id", plan.toDeactivate.map((c) => c.id));
    if (error) throw error;
  }
}
