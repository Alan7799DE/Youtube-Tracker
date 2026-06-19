import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { listDashboardRows } from "../data/dashboard";
import { summarize, type DashboardRow } from "../lib/dashboard";
import { dashboardRowBadge } from "../lib/status";
import { toMessage } from "../lib/errors";

export function DashboardPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<DashboardRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDashboardRows(supabase).then(setRows).catch((e) => setError(toMessage(e)));
  }, []);

  const s = summarize(rows);

  return (
    <section>
      <h1>Dashboard</h1>
      {error && <p role="alert">{error}</p>}

      <div className="cards">
        <div className="card card--total"><span className="card-label">Total</span><span className="card-num">{s.total}</span></div>
        <div className="card card--ontrack"><span className="card-label">Al día</span><span className="card-num">{s.onTrack}</span></div>
        <div className="card card--attention"><span className="card-label">Requieren atención</span><span className="card-num">{s.attention}</span></div>
        <div className="card card--pending"><span className="card-label">Pendientes</span><span className="card-num">{s.pending}</span></div>
      </div>

      <table>
        <thead>
          <tr><th>Campaña</th><th>Canal</th><th>Estado</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const badge = dashboardRowBadge(r.status, r.hasVideoInReview);
            return (
              <tr
                key={r.id}
                onClick={() => r.lastVideoId && navigate(`/videos/${r.lastVideoId}`)}
                style={{ cursor: r.lastVideoId ? "pointer" : "default" }}
              >
                <td>{r.campaignName}</td>
                <td>{r.channelName}</td>
                <td><span className={`badge badge-${badge.tone}`}>{badge.label}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
