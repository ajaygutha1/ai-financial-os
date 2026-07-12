"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { AIRecommendation } from "@/types/api";

export function useRecommendations() {
  return useQuery({
    queryKey: queryKeys.aiRecommendations,
    queryFn: () => apiFetch<AIRecommendation[]>("/api/v1/ai/recommendations"),
  });
}
