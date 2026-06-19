import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../lib/supabase", () => ({ supabase: {} }));
vi.mock("../data/channels", () => ({ listChannels: vi.fn().mockResolvedValue([]) }));
vi.mock("../data/campaigns", () => ({ createCampaign: vi.fn().mockResolvedValue("camp1") }));

import { createCampaign } from "../data/campaigns";
import { CampaignEditor } from "./CampaignEditor";

describe("CampaignEditor", () => {
  beforeEach(() => vi.clearAllMocks());

  it("no guarda sin plazo y muestra el error de validación", async () => {
    render(<MemoryRouter><CampaignEditor /></MemoryRouter>);
    // completar marca y nombre, dejar el plazo vacío
    fireEvent.change(screen.getByLabelText("Marca"), { target: { value: "Acme" } });
    fireEvent.change(screen.getByLabelText("Nombre"), { target: { value: "Lanzamiento" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar campaña" }));

    await waitFor(() => expect(screen.getByText("Falta el plazo (fecha de fin).")).toBeTruthy());
    expect(createCampaign).not.toHaveBeenCalled();
  });
});
