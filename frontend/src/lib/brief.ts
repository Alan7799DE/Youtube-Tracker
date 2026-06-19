import type { RequirementType } from "./types";

export type RequirementCode = "R1" | "R2" | "R3" | "R4" | "R5";

export interface CampaignForm {
  brand: string;
  name: string;
  endsAt: string; // ISO date; obligatorio
  gameName: string;
  expectedLink: string;
  code: string;
  requirements: Record<RequirementCode, boolean>;
}

export interface RequirementInput {
  code: RequirementCode;
  type: RequirementType;
  spec: Record<string, unknown>;
  method: "deterministic" | "llm" | "human";
  required: boolean;
}

// Mapea cada requisito elegido a su fila: tipo, método y spec según el código.
export function briefToRequirements(form: CampaignForm): RequirementInput[] {
  const out: RequirementInput[] = [];
  const r = form.requirements;
  if (r.R1) out.push({ code: "R1", type: "link_in_desc", spec: { expected_link: form.expectedLink }, method: "deterministic", required: true });
  if (r.R2) out.push({ code: "R2", type: "code_in_desc", spec: { code: form.code }, method: "deterministic", required: true });
  if (r.R3) out.push({ code: "R3", type: "mention_name", spec: { game_name: form.gameName }, method: "llm", required: true });
  if (r.R4) out.push({ code: "R4", type: "describe_game", spec: { game_name: form.gameName }, method: "llm", required: true });
  if (r.R5) out.push({ code: "R5", type: "show_gameplay", spec: {}, method: "human", required: true });
  return out;
}

export function validateCampaignForm(form: CampaignForm): string[] {
  const errors: string[] = [];
  if (!form.brand.trim()) errors.push("Falta la marca.");
  if (!form.name.trim()) errors.push("Falta el nombre de la campaña.");
  if (!form.endsAt.trim()) errors.push("Falta el plazo (fecha de fin).");
  if (form.requirements.R1 && !form.expectedLink.trim()) errors.push("R1 elegido pero falta el link esperado.");
  if (form.requirements.R2 && !form.code.trim()) errors.push("R2 elegido pero falta el código.");
  if ((form.requirements.R3 || form.requirements.R4) && !form.gameName.trim())
    errors.push("R3/R4 elegidos pero falta el nombre del juego.");
  return errors;
}
