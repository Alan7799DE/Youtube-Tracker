import { describe, it, expect } from "vitest";
import { channelStatusBadge, dashboardRowBadge } from "./status";

describe("channelStatusBadge", () => {
  it("verified -> Compliant/success", () => {
    expect(channelStatusBadge("verified")).toEqual({ label: "Compliant", tone: "success" });
  });
  it("incomplete -> Incomplete/warning", () => {
    expect(channelStatusBadge("incomplete")).toEqual({ label: "Incomplete", tone: "warning" });
  });
  it("failed -> Not met/danger", () => {
    expect(channelStatusBadge("failed")).toEqual({ label: "Not met", tone: "danger" });
  });
  it("pending -> Pending/neutral", () => {
    expect(channelStatusBadge("pending")).toEqual({ label: "Pending", tone: "neutral" });
  });
});

describe("dashboardRowBadge", () => {
  it("muestra 'In review' cuando hay un video en review y sigue pending", () => {
    expect(dashboardRowBadge("pending", true)).toEqual({ label: "In review", tone: "info" });
  });
  it("usa el estado del canal-campaña si no hay review pendiente", () => {
    expect(dashboardRowBadge("verified", false)).toEqual({ label: "Compliant", tone: "success" });
  });
  it("un estado terminal gana sobre el review", () => {
    expect(dashboardRowBadge("verified", true)).toEqual({ label: "Compliant", tone: "success" });
  });
  it("el review solo aplica a pending, no a incomplete ni failed", () => {
    expect(dashboardRowBadge("incomplete", true)).toEqual({ label: "Incomplete", tone: "warning" });
    expect(dashboardRowBadge("failed", true)).toEqual({ label: "Not met", tone: "danger" });
  });
});
