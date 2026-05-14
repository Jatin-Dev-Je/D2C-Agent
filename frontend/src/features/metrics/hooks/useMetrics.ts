import { useQuery } from "@tanstack/react-query";
import {
  getMetricSummary,
  getMetricCompare,
  getMetricRoas,
  getMetricCampaigns,
} from "@/lib/api/endpoints";
import { QUERY_KEYS, DEFAULT_QUERY_STALE_TIME } from "@/constants";
import type { MetricName } from "@/constants";

export function useMetricSummary(
  metric: MetricName,
  start: string,
  end: string,
  enabled = true,
) {
  return useQuery({
    queryKey: QUERY_KEYS.metricSummary(metric, start, end),
    queryFn: ({ signal }) => getMetricSummary(metric, start, end, signal),
    staleTime: DEFAULT_QUERY_STALE_TIME,
    enabled: enabled && !!metric && !!start && !!end,
    retry: 1,
  });
}

export function useMetricCompare(
  metric: MetricName,
  currentStart: string,
  currentEnd: string,
  previousStart: string,
  previousEnd: string,
  enabled = true,
) {
  return useQuery({
    queryKey: QUERY_KEYS.metricCompare(metric, currentStart, currentEnd, previousStart, previousEnd),
    queryFn: ({ signal }) =>
      getMetricCompare(metric, currentStart, currentEnd, previousStart, previousEnd, signal),
    staleTime: DEFAULT_QUERY_STALE_TIME,
    enabled: enabled && !!metric && !!currentStart && !!currentEnd,
    retry: 1,
  });
}

export function useMetricRoas(start: string, end: string, enabled = true) {
  return useQuery({
    queryKey: QUERY_KEYS.metricRoas(start, end),
    queryFn: ({ signal }) => getMetricRoas(start, end, signal),
    staleTime: DEFAULT_QUERY_STALE_TIME,
    enabled: enabled && !!start && !!end,
    retry: 1,
  });
}

export function useMetricCampaigns(start: string, end: string, limit = 100, enabled = true) {
  return useQuery({
    queryKey: QUERY_KEYS.metricCampaigns(start, end),
    queryFn: ({ signal }) => getMetricCampaigns(start, end, limit, signal),
    staleTime: DEFAULT_QUERY_STALE_TIME,
    enabled: enabled && !!start && !!end,
    retry: 1,
  });
}
