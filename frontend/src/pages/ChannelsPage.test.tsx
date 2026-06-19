import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("../lib/supabase", () => ({ supabase: {} }));
vi.mock("../data/channels", () => ({
  listChannels: vi.fn(),
  applyReconcilePlan: vi.fn(),
}));
vi.mock("../data/imports", () => ({ listImportRuns: vi.fn().mockResolvedValue([]) }));

import { listChannels } from "../data/channels";
import { ChannelsPage } from "./ChannelsPage";

describe("ChannelsPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renderiza una fila por canal y resalta los no resueltos", async () => {
    (listChannels as any).mockResolvedValue([
      { id: "c1", source_url: "https://youtube.com/@a", name: "Canal A", resolution_status: "resolved", is_active: true },
      { id: "c2", source_url: "https://youtube.com/@b", name: null, resolution_status: "unresolved", is_active: true },
    ]);
    render(<ChannelsPage />);

    await waitFor(() => expect(screen.getByText("https://youtube.com/@a")).toBeTruthy());
    expect(screen.getByText("https://youtube.com/@b")).toBeTruthy();
    // el no resuelto aparece marcado como "Unresolved"
    expect(screen.getByText("Unresolved")).toBeTruthy();
  });

  it("sin canales muestra el estado vacío de imports", async () => {
    (listChannels as any).mockResolvedValue([]);
    render(<ChannelsPage />);
    await waitFor(() => expect(screen.getByText("No imports yet.")).toBeTruthy());
  });
});
