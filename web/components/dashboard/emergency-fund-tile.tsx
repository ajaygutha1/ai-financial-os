"use client";

import { AnalyticsCard } from "@/components/dashboard/analytics-card";
import { Badge } from "@/components/ui/badge";
import { useEmergencyFund } from "@/hooks/use-emergency-fund";
import { formatCurrency } from "@/lib/format";
import type { EmergencyFundHealthTier } from "@/types/api";

const TIER_LABEL: Record<EmergencyFundHealthTier, string> = {
  unknown: "Not enough data",
  critical: "Critical",
  low: "Low",
  adequate: "Adequate",
  strong: "Strong",
};

const TIER_VARIANT: Record<
  EmergencyFundHealthTier,
  "default" | "secondary" | "destructive" | "outline"
> = {
  unknown: "outline",
  critical: "destructive",
  low: "secondary",
  adequate: "default",
  strong: "default",
};

export function EmergencyFundTile({ className }: { className?: string }) {
  const { data, isPending, isError } = useEmergencyFund(3);

  return (
    <AnalyticsCard
      title="Emergency fund"
      className={className}
      isPending={isPending}
      isError={isError}
    >
      {data ? (
        <div className="space-y-3">
          <div className="flex items-baseline justify-between">
            <span className="font-heading text-3xl tabular-nums tracking-tight">
              {data.months_of_coverage
                ? `${Number.parseFloat(data.months_of_coverage).toFixed(1)} mo`
                : "—"}
            </span>
            <Badge variant={TIER_VARIANT[data.health_tier]}>{TIER_LABEL[data.health_tier]}</Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            {formatCurrency(data.liquid_assets)} liquid vs.{" "}
            {formatCurrency(data.average_monthly_expenses)}/mo average spend
          </p>
        </div>
      ) : null}
    </AnalyticsCard>
  );
}
