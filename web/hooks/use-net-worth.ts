"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { NetWorthResponse } from "@/types/api";

export function useNetWorth() {
  return useQuery({
    queryKey: queryKeys.netWorth,
    queryFn: () => apiFetch<NetWorthResponse>("/api/v1/analytics/net-worth"),
  });
}
