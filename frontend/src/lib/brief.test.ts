import { describe, it, expect } from "vitest";
import { briefToRequirements, validateCampaignForm, type CampaignForm } from "./brief";

const base: CampaignForm = {
  brand: "Acme",
  name: "Lanzamiento",
  endsAt: "2026-07-01",
  gameName: "MiJuego",
  expectedLink: "https://dl.game/x",
  code: "GAMER20",
  requirements: { R1: true, R2: true, R3: true, R4: false, R5: true },
};

describe("briefToRequirements", () => {
  it("mapea solo los requisitos elegidos a filas tipadas con su spec/method", () => {
    expect(briefToRequirements(base)).toEqual([
      { code: "R1", type: "link_in_desc", spec: { expected_link: "https://dl.game/x" }, method: "deterministic", required: true },
      { code: "R2", type: "code_in_desc", spec: { code: "GAMER20" }, method: "deterministic", required: true },
      { code: "R3", type: "mention_name", spec: { game_name: "MiJuego" }, method: "llm", required: true },
      { code: "R5", type: "show_gameplay", spec: {}, method: "human", required: true },
    ]);
  });
});

describe("validateCampaignForm", () => {
  it("un form completo no tiene errores", () => {
    expect(validateCampaignForm(base)).toEqual([]);
  });
  it("exige el plazo (ends_at)", () => {
    expect(validateCampaignForm({ ...base, endsAt: "" })).toContain("Falta el plazo (fecha de fin).");
  });
  it("exige el link si R1 está elegido", () => {
    expect(validateCampaignForm({ ...base, expectedLink: "" })).toContain("R1 elegido pero falta el link esperado.");
  });
  it("exige el código si R2 está elegido", () => {
    expect(validateCampaignForm({ ...base, code: "" })).toContain("R2 elegido pero falta el código.");
  });
  it("exige el nombre del juego si R3/R4 están elegidos", () => {
    const form = { ...base, gameName: "", requirements: { ...base.requirements, R4: true } };
    expect(validateCampaignForm(form)).toContain("R3/R4 elegidos pero falta el nombre del juego.");
  });
  it("no exige link/código si esos requisitos no están elegidos", () => {
    const form = {
      ...base,
      expectedLink: "",
      code: "",
      requirements: { R1: false, R2: false, R3: true, R4: false, R5: false },
    };
    expect(validateCampaignForm(form)).toEqual([]);
  });
});

describe("briefToRequirements (más casos)", () => {
  it("R4 mapea a describe_game (llm) con el nombre del juego", () => {
    const form = { ...base, requirements: { R1: false, R2: false, R3: false, R4: true, R5: false } };
    expect(briefToRequirements(form)).toEqual([
      { code: "R4", type: "describe_game", spec: { game_name: "MiJuego" }, method: "llm", required: true },
    ]);
  });
  it("sin requisitos elegidos -> lista vacía", () => {
    const form = { ...base, requirements: { R1: false, R2: false, R3: false, R4: false, R5: false } };
    expect(briefToRequirements(form)).toEqual([]);
  });
});
