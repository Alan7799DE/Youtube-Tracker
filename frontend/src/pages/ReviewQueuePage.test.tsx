import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

vi.mock("../lib/supabase", () => ({ supabase: {} }));
vi.mock("../auth/useAuth", () => ({ useAuth: () => ({ user: { id: "u1" }, loading: false }) }));
vi.mock("../data/reviews", () => ({
  listReviewQueue: vi.fn(),
  insertReview: vi.fn().mockResolvedValue(undefined),
}));

import { listReviewQueue, insertReview } from "../data/reviews";
import { ReviewQueuePage } from "./ReviewQueuePage";

describe("ReviewQueuePage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("aprobar inserta la review con el reviewer y el gameplay confirmado", async () => {
    (listReviewQueue as any)
      .mockResolvedValueOnce([
        { verificationId: "ver1", videoId: "v1", youtubeVideoId: "YT1", title: "t", campaignName: "Camp" },
      ])
      .mockResolvedValueOnce([]);

    render(<ReviewQueuePage />);
    await waitFor(() => expect(screen.getByText("Camp")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Muestra gameplay"));
    fireEvent.click(screen.getByRole("button", { name: "Aprobar" }));

    await waitFor(() =>
      expect(insertReview).toHaveBeenCalledWith(expect.anything(), {
        verificationId: "ver1",
        reviewerId: "u1",
        pass: true,
        confirmedGameplay: true,
      })
    );
  });

  it("cola vacía muestra el estado feliz", async () => {
    (listReviewQueue as any).mockResolvedValue([]);
    render(<ReviewQueuePage />);
    await waitFor(() => expect(screen.getByText("No hay nada para revisar. 🎉")).toBeTruthy());
  });
});
