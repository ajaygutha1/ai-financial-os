"use client";

import { Trash2 } from "lucide-react";
import { toast } from "sonner";

import { AnalyticsCard } from "@/components/dashboard/analytics-card";
import { NewGoalDialog } from "@/components/dashboard/new-goal-dialog";
import { Button } from "@/components/ui/button";
import { useDeleteGoal, useGoals } from "@/hooks/use-goals";
import { ApiError } from "@/lib/api-client";
import { formatCurrency } from "@/lib/format";

export function GoalsCard({ className }: { className?: string }) {
  const { data, isPending, isError } = useGoals();
  const deleteGoal = useDeleteGoal();

  const handleDelete = (goalId: string) => {
    deleteGoal.mutate(goalId, {
      onError: (error) => {
        toast.error(error instanceof ApiError ? error.message : "Couldn't delete this goal.");
      },
    });
  };

  return (
    <AnalyticsCard title="Goals" className={className} isPending={isPending} isError={isError}>
      <div className="space-y-4">
        {data && data.length > 0 ? (
          <ul className="space-y-4">
            {data.map((goal) => {
              const pct = Math.min(100, Math.round(Number.parseFloat(goal.progress_pct)));
              return (
                <li key={goal.id} className="space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{goal.name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {formatCurrency(goal.current_amount)} / {formatCurrency(goal.target_amount)}
                      </span>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="size-6"
                        onClick={() => handleDelete(goal.id)}
                        aria-label={`Delete ${goal.name}`}
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            No goals yet. Set a target to start tracking progress.
          </p>
        )}
        <NewGoalDialog />
      </div>
    </AnalyticsCard>
  );
}
