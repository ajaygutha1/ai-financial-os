"use client";

import { format } from "date-fns";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AnalyticsCard } from "@/components/dashboard/analytics-card";
import { useCashFlow } from "@/hooks/use-cash-flow";
import { formatCurrency } from "@/lib/format";

// Parsed with explicit y/m/d rather than `new Date(isoString)` -- the API
// sends bare "YYYY-MM-01" dates, and parsing those as UTC then rendering in a
// negative-UTC-offset timezone can roll the displayed month back by one.
function monthLabel(value: string): string {
  const [year, month] = value.split("-").map(Number);
  return format(new Date(year, month - 1, 1), "MMM");
}

// Compact axis labels ("$6k" rather than "$6,000.00") -- short enough that
// they don't get clipped against the card edge at the chart's narrow width.
function formatAxisValue(value: number): string {
  if (Math.abs(value) >= 1000) return `$${(value / 1000).toFixed(0)}k`;
  return `$${value.toFixed(0)}`;
}

export function CashFlowChart({ className }: { className?: string }) {
  const { data, isPending, isError } = useCashFlow(6);

  const chartData =
    data?.months.map((m) => ({
      month: monthLabel(m.month),
      income: Number.parseFloat(m.income),
      expenses: Number.parseFloat(m.expenses),
      net: Number.parseFloat(m.net),
    })) ?? [];

  return (
    <AnalyticsCard
      title="Cash flow"
      className={className}
      isPending={isPending}
      isError={isError}
    >
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ left: 0, right: 8, top: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="month"
              tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 12, fill: "var(--muted-foreground)" }}
              axisLine={false}
              tickLine={false}
              width={48}
              tickFormatter={formatAxisValue}
            />
            <Tooltip
              formatter={(value) => formatCurrency(Number(value))}
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                fontSize: 12,
              }}
            />
            <Bar dataKey="income" name="Income" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
            <Bar dataKey="expenses" name="Expenses" fill="var(--chart-3)" radius={[4, 4, 0, 0]} />
            <Line
              type="monotone"
              dataKey="net"
              name="Net"
              stroke="var(--foreground)"
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </AnalyticsCard>
  );
}
