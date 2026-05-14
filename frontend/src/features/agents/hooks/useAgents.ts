import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { getAgentLogs, triggerAgent } from "@/lib/api/endpoints";
import { QUERY_KEYS, AGENT_LOGS_PAGE_SIZE } from "@/constants";

export function useAgentLogs(offset = 0) {
  return useQuery({
    queryKey: QUERY_KEYS.agentLogs(offset),
    queryFn: ({ signal }) => getAgentLogs(AGENT_LOGS_PAGE_SIZE, offset, signal),
    staleTime: 30_000,
    retry: 1,
  });
}

export function useTriggerAgent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (signal?: AbortSignal) => triggerAgent(signal),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["agent-logs"] });
      const hasFindings =
        data.findings &&
        data.findings.length > 0 &&
        !data.findings.includes("stable");

      toast.success(hasFindings ? "Agent found anomalies" : "Agent run complete", {
        description: data.proposed_action,
      });
    },
    onError: () => {
      toast.error("Agent run failed", {
        description: "Check your connection and try again.",
      });
    },
  });
}
