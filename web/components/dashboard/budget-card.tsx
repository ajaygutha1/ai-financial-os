"use client";

import { Trash2 } from "lucide-react";
import { toast } from "sonner";

import { AnalyticsCard } from "@/components/dashboard/analytics-card";
import { SetBudgetDialog } from "@/components/dashboard/set-budget-dialog";
import { Button } from "@/components/ui/button";
import { useBudgetTargets, useBudgetVsActual, useDeleteBudgetTarget } from "@/hooks/use-budget";
import { ApiError } from "@/lib/api-client";
import { formatCurrency } from "@/lib/format";

export function BudgetCard({ className }: { className?: string }) {
  const { data: actual, isPending, isError } = useBudgetVsActual();
  const { data: targets } = useBudgetTargets();
  const deleteTarget = useDeleteBudgetTarget();

  const handleDelete = (targetId: string) => {
    deleteTarget.mutate(targetId, {
      onError: (error) => {
        toast.error(error instanceof ApiError ? error.message : "Couldn't remove this target.");
      },
    });
  };

  return (
    <AnalyticsCard title="Budget" className={className} isPending={isPending} isError={isError}>
      <div className="space-y-4">
        {actual && actual.categories.length > 0 ? (
          <ul className="space-y-3">
            {actual.categories.map((c) => {
              const pct = Math.min(100, Math.round(Number.parseFloat(c.pct_used)));
              const over = Number.parseFloat(c.remaining) < 0;
              const targetId = targets?.find((t) => t.category_id === c.category_id)?.id;
              return (
                <li key={c.category_id} className="space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{c.category_name}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground tabular-nums">
                        {formatCurrency(c.actual_amount)} / {formatCurrency(c.target_amount)}
                      </span>
                      {targetId && (
                        <Button
                          size="icon"
                          variant="ghost"
                          className="size-6"
                          onClick={() => handleDelete(targetId)}
                          aria-label={`Remove ${c.category_name} budget`}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      )}
                    </div>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full rounded-full transition-all ${over ? "bg-destructive" : "bg-primary"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            No budget targets set yet. Set a monthly target per category to track spending
            against it.
          </p>
        )}
        <SetBudgetDialog />
      </div>
    </AnalyticsCard>
  );
}
