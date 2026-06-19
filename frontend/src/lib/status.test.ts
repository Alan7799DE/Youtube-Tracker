import { describe, it, expect } from "vitest";
import { channelStatusBadge, dashboardRowBadge } from "./status";

describe("channelStatusBadge", () => {
  it("verified -> Cumple/success", () => {
    expect(channelStatusBadge("verified")).toEqual({ label: "Cumple", tone: "success" });
  });
  it("incomplete -> Incompleto/warning", () => {
    expect(channelStatusBadge("incomplete")).toEqual({ label: "Incompleto", tone: "warning" });
  });
  it("failed -> No cumplió/danger", () => {
    expect(channelStatusBadge("failed")).toEqual({ label: "No cumplió", tone: "danger" });
  });
  it("pending -> Pendiente/neutral", () => {
    expect(channelStatusBadge("pending")).toEqual({ label: "Pendiente", tone: "neutral" });
  });
});

describe("dashboardRowBadge", () => {
  it("muestra 'En revisión' cuando hay un video en review y sigue pending", () => {
    expect(dashboardRowBadge("pending", true)).toEqual({ label: "En revisión", tone: "info" });
  });
  it("usa el estado del canal-campaña si no hay review pendiente", () => {
    expect(dashboardRowBadge("verified", false)).toEqual({ label: "Cumple", tone: "success" });
  });
  it("un estado terminal gana sobre el review", () => {
    expect(dashboardRowBadge("verified", true)).toEqual({ label: "Cumple", tone: "success" });
  });
  it("el review solo aplica a pending, no a incomplete ni failed", () => {
    expect(dashboardRowBadge("incomplete", true)).toEqual({ label: "Incompleto", tone: "warning" });
    expect(dashboardRowBadge("failed", true)).toEqual({ label: "No cumplió", tone: "danger" });
  });
});
