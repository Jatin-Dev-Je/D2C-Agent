import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getConnectorHealth, triggerConnectorSync } from "@/lib/api/endpoints";
import { QUERY_KEYS } from "@/constants";

export function useConnectorHealth() {
  return useQuery({
    queryKey: QUERY_KEYS.connectorHealth,
    queryFn: ({ signal }) => getConnectorHealth(signal),
    staleTime: 60_000,
    retry: 1,
  });
}

export function useTriggerSync() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (signal?: AbortSignal) => triggerConnectorSync(signal),
    onSuccess: (data) => {
      toast.success("Sync started", {
        description: `Syncing ${data.connectors.join(", ")} in background.`,
      });
      // Refresh health after a short delay
      setTimeout(() => {
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.connectorHealth });
      }, 3000);
    },
    onError: () => {
      toast.error("Sync failed", { description: "Could not start connector sync." });
    },
  });
}
