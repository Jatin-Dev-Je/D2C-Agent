import { useQuery } from "@tanstack/react-query";
import { getDashboard } from "@/lib/api/endpoints";
import { QUERY_KEYS, DEFAULT_QUERY_STALE_TIME } from "@/constants";

export function useDashboard() {
  return useQuery({
    queryKey: QUERY_KEYS.dashboard,
    queryFn: ({ signal }) => getDashboard(signal),
    staleTime: DEFAULT_QUERY_STALE_TIME,
    retry: 1,
  });
}
