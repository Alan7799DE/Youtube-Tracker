import type { SupabaseClient } from "@supabase/supabase-js";

export interface ImportRun {
  id: string;
  created_at: string;
  added: number | null;
  deactivated: number | null;
  unresolved: number | null;
}

export async function listImportRuns(client: SupabaseClient, limit = 10): Promise<ImportRun[]> {
  const { data, error } = await client
    .from("import_runs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(limit);
  if (error) throw error;
  return (data ?? []) as ImportRun[];
}
