import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

vi.mock("../lib/supabase", () => ({ supabase: {} }));
vi.mock("../data/videos", () => ({ getVideoDetail: vi.fn() }));

import { getVideoDetail } from "../data/videos";
import { VideoDetailPage } from "./VideoDetailPage";

describe("VideoDetailPage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("muestra el veredicto por campaña y un link al timestamp de la evidencia", async () => {
    (getVideoDetail as any).mockResolvedValue({
      id: "v1",
      title: "Mi video",
      youtubeVideoId: "YT1",
      verdicts: [
        {
          campaignName: "Camp",
          overallStatus: "pass",
          results: [{ code: "R3", met: true, confidence: 0.9, evidence: "menciona el juego", evidenceTimestampS: 75 }],
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/videos/v1"]}>
        <Routes><Route path="/videos/:id" element={<VideoDetailPage />} /></Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByText("Camp — Cumple")).toBeTruthy());
    const link = screen.getByRole("link", { name: "ver minuto" }) as HTMLAnchorElement;
    expect(link.href).toBe("https://youtu.be/YT1?t=75");
  });
});
