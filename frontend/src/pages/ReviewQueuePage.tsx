import { useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import { useAuth } from "../auth/useAuth";
import { listReviewQueue, insertReview, type ReviewItem } from "../data/reviews";
import { youtubeTimestampUrl } from "../lib/youtube";
import { toMessage } from "../lib/errors";

export function ReviewQueuePage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [gameplay, setGameplay] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    setItems(await listReviewQueue(supabase));
  }

  useEffect(() => {
    reload().catch((e) => setError(toMessage(e)));
  }, []);

  async function decide(item: ReviewItem, pass: boolean) {
    if (!user) return;
    try {
      await insertReview(supabase, {
        verificationId: item.verificationId,
        reviewerId: user.id,
        pass,
        confirmedGameplay: gameplay[item.verificationId] ?? false,
      });
      await reload();
    } catch (e) {
      setError(toMessage(e));
    }
  }

  return (
    <section>
      <h1>Review queue</h1>
      {error && <p role="alert">{error}</p>}
      {items.length === 0 ? (
        <p>Nothing to review. 🎉</p>
      ) : (
        <ul className="review-list">
          {items.map((item) => (
            <li key={item.verificationId} className="review-item">
              <div>
                <strong>{item.campaignName}</strong> — {item.title ?? "(untitled)"}{" "}
                <a href={youtubeTimestampUrl(item.youtubeVideoId, null)} target="_blank" rel="noreferrer">watch video</a>
              </div>
              <p className="hint">All text checks pass; confirm the gameplay (R5).</p>
              <label>
                <input
                  type="checkbox"
                  checked={gameplay[item.verificationId] ?? false}
                  onChange={(e) => setGameplay((g) => ({ ...g, [item.verificationId]: e.target.checked }))}
                />
                Shows gameplay
              </label>
              <div className="actions">
                <button type="button" onClick={() => decide(item, true)}>Approve</button>
                <button type="button" onClick={() => decide(item, false)}>Reject</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
