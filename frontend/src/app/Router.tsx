import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { ErrorBoundary } from "@/components/shared/ErrorBoundary";
import { DashboardPage } from "@/pages/DashboardPage";
import { ChatPage } from "@/pages/ChatPage";
import { AgentsPage } from "@/pages/AgentsPage";
import { MetricsPage } from "@/pages/MetricsPage";
import { ConnectorsPage } from "@/pages/ConnectorsPage";
import { SettingsPage } from "@/pages/SettingsPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    errorElement: (
      <ErrorBoundary>
        <div className="flex h-screen items-center justify-center text-muted-foreground text-sm">
          Page not found
        </div>
      </ErrorBoundary>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      {
        path: "dashboard",
        element: (
          <ErrorBoundary>
            <DashboardPage />
          </ErrorBoundary>
        ),
      },
      {
        path: "chat",
        element: (
          <ErrorBoundary>
            <ChatPage />
          </ErrorBoundary>
        ),
      },
      {
        path: "agents",
        element: (
          <ErrorBoundary>
            <AgentsPage />
          </ErrorBoundary>
        ),
      },
      {
        path: "metrics",
        element: (
          <ErrorBoundary>
            <MetricsPage />
          </ErrorBoundary>
        ),
      },
      {
        path: "connectors",
        element: (
          <ErrorBoundary>
            <ConnectorsPage />
          </ErrorBoundary>
        ),
      },
      {
        path: "settings",
        element: (
          <ErrorBoundary>
            <SettingsPage />
          </ErrorBoundary>
        ),
      },
    ],
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
