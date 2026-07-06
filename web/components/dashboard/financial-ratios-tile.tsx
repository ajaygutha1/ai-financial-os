"use client";

import { AnalyticsCard } from "@/components/dashboard/analytics-card";
import { useBurnRate } from "@/hooks/use-burn-rate";
import { useRatios } from "@/hooks/use-ratios";
import { formatCurrency } from "@/lib/format";

function formatPercent(value: string | null): string {
  if (value === null) return "—";
  return `${(Number.parseFloat(value) * 100).toFixed(1)}%`;
}

function formatMonths(value: string | null): string {
  if (value === null) return "—";
  return `${Number.parseFloat(value).toFixed(1)} mo`;
}

export function FinancialRatiosTile({ className }: { className?: string }) {
  const ratios = useRatios(6);
  const burnRate = useBurnRate(3);

  const isPending = ratios.isPending || burnRate.isPending;
  const isError = ratios.isError || burnRate.isError;

  return (
    <AnalyticsCard
      title="Financial ratios"
      className={className}
      isPending={isPending}
      isError={isError}
    >
      {ratios.data && burnRate.data ? (
        <div className="grid grid-cols-2 gap-4">
          <Stat label="Savings rate" value={formatPercent(ratios.data.savings_rate)} />
          <Stat
            label={burnRate.data.is_burning ? "Burn rate" : "Net saving"}
            value={formatCurrency(Math.abs(Number.parseFloat(burnRate.data.average_monthly_burn)))}
          />
          <Stat label="Debt / income" value={formatPercent(ratios.data.debt_to_annual_income)} />
          <Stat label="Liquidity" value={formatMonths(ratios.data.liquidity_ratio_months)} />
        </div>
      ) : null}
    </AnalyticsCard>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-heading text-xl tabular-nums tracking-tight">{value}</p>
    </div>
  );
}
