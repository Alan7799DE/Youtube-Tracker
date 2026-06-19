import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AuthProvider } from "./AuthProvider";
import { useAuth } from "./useAuth";

vi.mock("../lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: { user: { id: "u1", email: "a@b.com" } } } }),
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
    render(<AuthProvider><Probe /></AuthProvider>);
    await waitFor(() => expect(screen.getByText("a@b.com")).toBeTruthy());
  });
});
