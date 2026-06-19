import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { listCampaigns, closeCampaign } from "../data/campaigns";
import type { Campaign } from "../lib/types";
import { toMessage } from "../lib/errors";

export function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    setCampaigns(await listCampaigns(supabase));
  }

  useEffect(() => {
    reload().catch((e) => setError(toMessage(e)));
  }, []);

  async function onClose(id: string) {
    try {
      await closeCampaign(supabase, id);
      await reload();
    } catch (e) {
      setError(toMessage(e));
    }
  }

  return (
    <section>
      <header className="page-head">
        <h1>Campaigns</h1>
        <Link className="btn" to="/campaigns/new">New campaign</Link>
      </header>
      {error && <p role="alert">{error}</p>}
      <table>
        <thead>
          <tr><th>Brand</th><th>Name</th><th>Deadline</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          {campaigns.map((c) => (
            <tr key={c.id}>
              <td>{c.brand}</td>
              <td>{c.name}</td>
              <td>{c.ends_at}</td>
              <td>{c.status === "active" ? "Active" : "Closed"}</td>
              <td>
                {c.status === "active" && (
                  <button type="button" onClick={() => onClose(c.id)}>Close</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
