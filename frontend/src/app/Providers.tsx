import { type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DEFAULT_QUERY_STALE_TIME, DEFAULT_QUERY_GC_TIME } from "@/constants";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: DEFAULT_QUERY_STALE_TIME,
      gcTime: DEFAULT_QUERY_GC_TIME,
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={300}>
        {children}
        <Toaster
          position="bottom-right"
          theme="light"
          toastOptions={{
            classNames: {
              toast: "bg-card border-border text-foreground shadow-sm",
              description: "text-muted-foreground",
            },
          }}
        />
      </TooltipProvider>
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  );
}
