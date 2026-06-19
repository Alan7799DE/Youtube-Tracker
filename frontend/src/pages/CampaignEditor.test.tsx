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
    fireEvent.change(screen.getByLabelText("Brand"), { target: { value: "Acme" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Launch" } });
    fireEvent.click(screen.getByRole("button", { name: "Save campaign" }));

    await waitFor(() => expect(screen.getByText("Deadline (end date) is required.")).toBeTruthy());
    expect(createCampaign).not.toHaveBeenCalled();
  });
});
