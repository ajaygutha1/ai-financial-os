"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { FinancialAdviceResponse } from "@/types/api";

export function useFinancialAdvice(agentSlug: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (message?: string) =>
      apiFetch<FinancialAdviceResponse>(`/api/v1/ai/${agentSlug}/advice`, {
        method: "POST",
        body: JSON.stringify({ message: message ?? null }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.aiRecommendations });
    },
  });
}
