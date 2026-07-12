"use client";

import { ArrowDownRight, ArrowUpRight, Minus, Sparkle } from "lucide-react";
import type { ComponentType } from "react";

import { AnalyticsCard } from "@/components/dashboard/analytics-card";
import { useExpenseTrends } from "@/hooks/use-expense-trends";
import { formatCurrency } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { CategoryTrendDirection } from "@/types/api";

const TREND_ICON: Record<CategoryTrendDirection, ComponentType<{ className?: string }>> = {
  rising: ArrowUpRight,
  falling: ArrowDownRight,
  steady: Minus,
  new: Sparkle,
};

// Rising spend gets the one splash of semantic color in an otherwise
// monochrome design system -- it's the one trend that's actually worth
// flagging as "notice this."
const TREND_CLASS: Record<CategoryTrendDirection, string> = {
  rising: "text-destructive",
  falling: "text-foreground",
  steady: "text-muted-foreground",
  new: "text-muted-foreground",
};

export function ExpenseTrendsCard({ className }: { className?: string }) {
  const { data, isPending, isError } = useExpenseTrends(4);

  return (
    <AnalyticsCard
      title="Expense trends"
      className={className}
      isPending={isPending}
      isError={isError}
    >
      {data ? (
        data.categories.length === 0 ? (
          <p className="text-sm text-muted-foreground">Not enough spending history yet.</p>
        ) : (
          <ul className="divide-y divide-border">
            {data.categories.slice(0, 5).map((category) => {
              const Icon = TREND_ICON[category.trend];
              return (
                <li
                  key={category.category}
                  className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0"
                >
                  <span className="text-sm">{category.category}</span>
                  <span className="flex items-center gap-2 tabular-nums">
                    <Icon className={cn("size-3.5", TREND_CLASS[category.trend])} />
                    <span className="text-sm font-medium">
                      {formatCurrency(category.latest_month_total)}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        )
      ) : null}
    </AnalyticsCard>
  );
}
