import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../lib/supabase", () => ({ supabase: {} }));
vi.mock("../data/dashboard", () => ({ listDashboardRows: vi.fn() }));

import { listDashboardRows } from "../data/dashboard";
import { DashboardPage } from "./DashboardPage";

describe("DashboardPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("muestra el resumen y una fila con su badge", async () => {
    (listDashboardRows as any).mockResolvedValue([
      { id: "cc1", campaignName: "Camp", channelName: "Canal A", status: "verified", hasVideoInReview: false, lastVideoId: "v1" },
    ]);
    render(<MemoryRouter><DashboardPage /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText("Canal A")).toBeTruthy());
    expect(screen.getByText("Cumple")).toBeTruthy();
    // tarjeta "Al día" con 1
    expect(screen.getByText("Al día")).toBeTruthy();
  });
});
