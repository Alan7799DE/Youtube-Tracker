import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { getVideoDetail, type VideoDetail } from "../data/videos";
import { youtubeTimestampUrl } from "../lib/youtube";
import { toMessage } from "../lib/errors";

const VERDICT_LABEL: Record<string, string> = { pass: "Cumple", fail: "No cumplió", review: "En revisión" };

export function VideoDetailPage() {
  const { id } = useParams();
  const [detail, setDetail] = useState<VideoDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    getVideoDetail(supabase, id).then(setDetail).catch((e) => setError(toMessage(e)));
  }, [id]);

  if (error) return <p role="alert">{error}</p>;
  if (!detail) return <p>Cargando…</p>;

  return (
    <section>
      <h1>{detail.title ?? "Video"}</h1>
      <p>
        <a href={youtubeTimestampUrl(detail.youtubeVideoId, null)} target="_blank" rel="noreferrer">
          Ver en YouTube
        </a>
      </p>

      {detail.verdicts.length === 0 && <p>Todavía no hay verificaciones para este video.</p>}

      {detail.verdicts.map((v, i) => (
        <article key={i} className="verdict">
          <h2>{v.campaignName} — {VERDICT_LABEL[v.overallStatus] ?? v.overallStatus}</h2>
          <ul className="checklist">
            {v.results.map((r) => (
              <li key={r.code}>
                <strong>{r.met ? "✓" : "✗"} {r.code}</strong>
                {r.confidence != null && <span> (confianza {Math.round(r.confidence * 100)}%)</span>}
                {r.evidence && <span> — “{r.evidence}”</span>}
                {r.evidenceTimestampS != null && (
                  <>
                    {" "}
                    <a href={youtubeTimestampUrl(detail.youtubeVideoId, r.evidenceTimestampS)} target="_blank" rel="noreferrer">
                      ver minuto
                    </a>
                  </>
                )}
              </li>
            ))}
          </ul>
        </article>
      ))}
    </section>
  );
}
