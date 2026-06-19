export interface ExistingChannel { id: string; source_url: string; is_active: boolean; }
export interface ReconcilePlan {
  toAdd: string[];
  toKeep: ExistingChannel[];
  toDeactivate: ExistingChannel[];
  toReactivate: ExistingChannel[];
}

const norm = (u: string) => u.trim().toLowerCase().replace(/\/+$/, "");

export function reconcile(newUrls: string[], existing: ExistingChannel[]): ReconcilePlan {
  const newSet = new Set(newUrls.map(norm));
  const existingNorms = new Set(existing.map((c) => norm(c.source_url)));

  const toAdd: string[] = [];
  const seen = new Set<string>();
  for (const u of newUrls) {
    const n = norm(u);
    if (!existingNorms.has(n) && !seen.has(n)) { seen.add(n); toAdd.push(u); }
  }

  const toKeep: ExistingChannel[] = [];
  const toDeactivate: ExistingChannel[] = [];
  const toReactivate: ExistingChannel[] = [];
  for (const c of existing) {
    const inNew = newSet.has(norm(c.source_url));
    if (inNew && c.is_active) toKeep.push(c);
    else if (inNew && !c.is_active) toReactivate.push(c);
    else if (!inNew && c.is_active) toDeactivate.push(c);
  }
  return { toAdd, toKeep, toDeactivate, toReactivate };
}
