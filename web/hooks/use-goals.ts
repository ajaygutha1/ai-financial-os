"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { Goal } from "@/types/api";

export interface CreateGoalInput {
  name: string;
  target_amount: string;
  target_date?: string | null;
  linked_account_id?: string | null;
  manual_current_amount?: string;
}

export interface UpdateGoalInput {
  name?: string;
  target_amount?: string;
  target_date?: string | null;
  manual_current_amount?: string;
  status?: string;
}

export function useGoals() {
  return useQuery({
    queryKey: queryKeys.goals,
    queryFn: () => apiFetch<Goal[]>("/api/v1/goals"),
  });
}

export function useCreateGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateGoalInput) =>
      apiFetch<Goal>("/api/v1/goals", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.goals });
    },
  });
}

export function useUpdateGoal(goalId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateGoalInput) =>
      apiFetch<Goal>(`/api/v1/goals/${goalId}`, {
        method: "PATCH",
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.goals });
    },
  });
}

export function useDeleteGoal() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (goalId: string) =>
      apiFetch<void>(`/api/v1/goals/${goalId}`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.goals });
    },
  });
}
