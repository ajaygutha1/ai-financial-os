"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { RatiosResponse } from "@/types/api";

export function useRatios(months = 6) {
  return useQuery({
    queryKey: queryKeys.ratios(months),
    queryFn: () => apiFetch<RatiosResponse>(`/api/v1/analytics/ratios?months=${months}`),
  });
}
