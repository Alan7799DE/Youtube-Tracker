import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "./AppShell";
import { RequireAuth } from "./RequireAuth";
import { DashboardPage } from "../pages/DashboardPage";
import { ChannelsPage } from "../pages/ChannelsPage";
import { CampaignsPage } from "../pages/CampaignsPage";
import { CampaignEditor } from "../pages/CampaignEditor";
import { VideoDetailPage } from "../pages/VideoDetailPage";
import { ReviewQueuePage } from "../pages/ReviewQueuePage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "channels", element: <ChannelsPage /> },
      { path: "campaigns", element: <CampaignsPage /> },
      { path: "campaigns/:id", element: <CampaignEditor /> },
      { path: "videos/:id", element: <VideoDetailPage /> },
      { path: "review", element: <ReviewQueuePage /> },
    ],
  },
]);
