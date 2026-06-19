import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AuthProvider } from "./AuthProvider";
import { useAuth } from "./useAuth";

const getSession = vi.fn();
vi.mock("../lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: (...args: unknown[]) => getSession(...args),
      onAuthStateChange: vi.fn().mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } }),
    },
  },
}));

function Probe() {
  const { user } = useAuth();
  return <div>{user ? user.email : "anon"}</div>;
}

describe("AuthProvider", () => {
  it("expone el usuario de la sesión", async () => {
    getSession.mockResolvedValue({ data: { session: { user: { id: "u1", email: "a@b.com" } } } });
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByText("a@b.com")).toBeTruthy());
  });

  it("si getSession falla, trata al usuario como anónimo (no se cuelga)", async () => {
    getSession.mockRejectedValue(new Error("network"));
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByText("anon")).toBeTruthy());
  });
});
