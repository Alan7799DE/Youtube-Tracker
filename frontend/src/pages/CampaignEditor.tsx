import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { createCampaign } from "../data/campaigns";
import { listChannels } from "../data/channels";
import { validateCampaignForm, type CampaignForm, type RequirementCode } from "../lib/brief";
import type { Channel } from "../lib/types";
import { toMessage } from "../lib/errors";

const REQUIREMENT_LABELS: Record<RequirementCode, string> = {
  R1: "Download link in the description",
  R2: "Promo code in the description",
  R3: "Mentions the game name",
  R4: "Talks about what the game is",
  R5: "Shows gameplay on screen",
};

const EMPTY: CampaignForm = {
  brand: "",
  name: "",
  endsAt: "",
  gameName: "",
  expectedLink: "",
  code: "",
  requirements: { R1: true, R2: true, R3: true, R4: false, R5: false },
};

export function CampaignEditor() {
  const navigate = useNavigate();
  const [form, setForm] = useState<CampaignForm>(EMPTY);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listChannels(supabase).then(setChannels).catch(() => setChannels([]));
  }, []);

  function set<K extends keyof CampaignForm>(key: K, value: CampaignForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function toggleReq(code: RequirementCode) {
    setForm((f) => ({ ...f, requirements: { ...f.requirements, [code]: !f.requirements[code] } }));
  }

  function toggleChannel(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validateCampaignForm(form);
    setErrors(errs);
    if (errs.length > 0) return;
    setSaving(true);
    try {
      await createCampaign(supabase, form, selected);
      navigate("/campaigns");
    } catch (err) {
      setErrors([toMessage(err)]);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <h1>New campaign</h1>

      {errors.length > 0 && (
        <ul role="alert">
          {errors.map((e) => <li key={e}>{e}</li>)}
        </ul>
      )}

      <label>Brand<input value={form.brand} onChange={(e) => set("brand", e.target.value)} /></label>
      <label>Name<input value={form.name} onChange={(e) => set("name", e.target.value)} /></label>
      <label>Deadline (end date)<input type="date" value={form.endsAt} onChange={(e) => set("endsAt", e.target.value)} /></label>

      <fieldset>
        <legend>Brief</legend>
        <label>Game name<input value={form.gameName} onChange={(e) => set("gameName", e.target.value)} /></label>
        <label>Expected link<input value={form.expectedLink} onChange={(e) => set("expectedLink", e.target.value)} /></label>
        <label>Code<input value={form.code} onChange={(e) => set("code", e.target.value)} /></label>
      </fieldset>

      <fieldset>
        <legend>Requirements to verify</legend>
        {(Object.keys(REQUIREMENT_LABELS) as RequirementCode[]).map((code) => (
          <label key={code}>
            <input type="checkbox" checked={form.requirements[code]} onChange={() => toggleReq(code)} />
            {code} — {REQUIREMENT_LABELS[code]}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Assign channels</legend>
        {channels.length === 0 ? (
          <p>No channels yet. Import channels first.</p>
        ) : (
          channels.map((c) => (
            <label key={c.id}>
              <input type="checkbox" checked={selected.includes(c.id)} onChange={() => toggleChannel(c.id)} />
              {c.name ?? c.source_url}
            </label>
          ))
        )}
      </fieldset>

      <button type="submit" disabled={saving}>{saving ? "Saving…" : "Save campaign"}</button>
    </form>
  );
}
