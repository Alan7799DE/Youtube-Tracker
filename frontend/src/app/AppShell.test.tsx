import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../lib/supabase", () => ({ supabase: { auth: { signOut: vi.fn() } } }));

import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("muestra los 4 menús principales y el botón de cerrar sesión", () => {
    render(<MemoryRouter><AppShell /></MemoryRouter>);
    for (const label of ["Dashboard", "Campañas", "Canales", "Revisión"]) {
      expect(screen.getByRole("link", { name: label })).toBeTruthy();
    }
    expect(screen.getByRole("button", { name: "Cerrar sesión" })).toBeTruthy();
  });
});
