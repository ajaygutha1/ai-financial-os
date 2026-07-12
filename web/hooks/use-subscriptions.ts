"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { SubscriptionsResponse } from "@/types/api";

export function useSubscriptions(months = 6) {
  return useQuery({
    queryKey: queryKeys.subscriptions(months),
    queryFn: () =>
      apiFetch<SubscriptionsResponse>(`/api/v1/analytics/subscriptions?months=${months}`),
  });
}
