import { useEffect, useRef, useState } from "react";
import { supabase } from "../lib/supabase";
import { listChannels, applyReconcilePlan } from "../data/channels";
import { listImportRuns, type ImportRun } from "../data/imports";
import { parseChannelsFile } from "../lib/parseChannels";
import { reconcile } from "../lib/reconcile";
import type { Channel } from "../lib/types";
import { toMessage } from "../lib/errors";

export function ChannelsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [imports, setImports] = useState<ImportRun[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function reload() {
    setChannels(await listChannels(supabase));
    setImports(await listImportRuns(supabase));
  }

  useEffect(() => {
    reload().catch((e) => setError(toMessage(e)));
  }, []);

  async function onImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const buf = await file.arrayBuffer();
      const urls = parseChannelsFile(buf);
      const plan = reconcile(urls, channels.map((c) => ({ id: c.id, source_url: c.source_url, is_active: c.is_active })));
      await applyReconcilePlan(supabase, plan);
      await reload();
    } catch (err) {
      setError(toMessage(err));
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const unresolved = channels.filter((c) => c.resolution_status === "unresolved");

  return (
    <section>
      <header className="page-head">
        <h1>Channels</h1>
        <label className="btn">
          {busy ? "Importing…" : "Import file"}
          <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" hidden disabled={busy} onChange={onImport} />
        </label>
      </header>

      {error && <p role="alert">{error}</p>}

      {unresolved.length > 0 && (
        <div className="callout-warning">
          <strong>{unresolved.length} unresolved channel(s)</strong> — the backend will resolve them, or fix the URL manually.
        </div>
      )}

      <table>
        <thead>
          <tr><th>URL</th><th>Handle / name</th><th>Resolution</th><th>Active</th></tr>
        </thead>
        <tbody>
          {channels.map((c) => (
            <tr key={c.id} className={c.resolution_status === "unresolved" ? "row-unresolved" : ""}>
              <td>{c.source_url}</td>
              <td>{c.handle ?? c.name ?? "—"}</td>
              <td>{c.resolution_status === "unresolved" ? "Unresolved" : c.resolution_status}</td>
              <td>{c.is_active ? "Yes" : "No"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Import history</h2>
      {imports.length === 0 ? (
        <p>No imports yet.</p>
      ) : (
        <ul>
          {imports.map((r) => (
            <li key={r.id}>
              {new Date(r.created_at).toLocaleString()} — +{r.added ?? 0} / −{r.deactivated ?? 0} / {r.unresolved ?? 0} unresolved
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
