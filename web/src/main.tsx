import "./styles/globals.css";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { router } from "./router";
import { ErrorBoundary } from "@/components/ErrorBoundary";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // Don't retry 401s — user needs to log in
        const msg = (error as Error)?.message || "";
        if (msg.includes("HTTP 401")) return false;
        return failureCount < 2;
      },
      staleTime: 5_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = document.getElementById("root");
if (!root) throw new Error("missing #root");

// Cloudflare edge injects script/style nodes into #root (email obfuscation,
// bot-fight, analytics). React 18 crashes if the container isn't empty at
// mount time ("Node.removeChild: not a child"). Purge before handing off.
while (root.lastChild) {
  try {
    root.removeChild(root.lastChild);
  } catch {
    break;
  }
}

createRoot(root).render(
  <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </ErrorBoundary>,
);
