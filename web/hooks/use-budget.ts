"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { BudgetTarget, BudgetVsActualResponse, Category } from "@/types/api";

export function useCategories() {
  return useQuery({
    queryKey: queryKeys.categories,
    queryFn: () => apiFetch<Category[]>("/api/v1/categories"),
  });
}

export function useBudgetTargets() {
  return useQuery({
    queryKey: queryKeys.budgetTargets,
    queryFn: () => apiFetch<BudgetTarget[]>("/api/v1/budget/targets"),
  });
}

export function useBudgetVsActual() {
  return useQuery({
    queryKey: queryKeys.budgetVsActual,
    queryFn: () => apiFetch<BudgetVsActualResponse>("/api/v1/analytics/budget-vs-actual"),
  });
}

export interface SetBudgetTargetInput {
  category_id: string;
  monthly_target_amount: string;
}

export function useSetBudgetTarget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: SetBudgetTargetInput) =>
      apiFetch<BudgetTarget>("/api/v1/budget/targets", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.budgetTargets });
      void queryClient.invalidateQueries({ queryKey: queryKeys.budgetVsActual });
    },
  });
}

export function useDeleteBudgetTarget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (targetId: string) =>
      apiFetch<void>(`/api/v1/budget/targets/${targetId}`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.budgetTargets });
      void queryClient.invalidateQueries({ queryKey: queryKeys.budgetVsActual });
    },
  });
}
