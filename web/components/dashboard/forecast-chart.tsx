"use client";

import { format } from "date-fns";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { AnalyticsCard } from "@/components/dashboard/analytics-card";
import { useForecast } from "@/hooks/use-forecast";
import { formatCurrency } from "@/lib/format";

function monthLabel(value: string): string {
  const [year, month] = value.split("-").map(Number);
  return format(new Date(year, month - 1, 1), "MMM");
}

function formatAxisValue(value: number): string {
  if (Math.abs(value) >= 1000) return `$${(value / 1000).toFixed(0)}k`;
  return `$${value.toFixed(0)}`;
}

export function ForecastChart({ className }: { className?: string }) {
  const { data, isPending, isError } = useForecast(6);

  const chartData = data
    ? [
        { month: "Now", projected: Number.parseFloat(data.current_net_worth) },
        ...data.projected_months.map((m) => ({
          month: monthLabel(m.month),
          projected: Number.parseFloat(m.projected_net_worth),
        })),
      ]
    : [];

  return (
    <AnalyticsCard
      title="Net worth forecast"
      className={className}
      isPending={isPending}
      isError={isError}
    >
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ left: 0, right: 8, top: 8 }}>
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
            <Line
              type="monotone"
              dataKey="projected"
              name="Projected net worth"
              stroke="var(--foreground)"
              strokeWidth={2}
              strokeDasharray="4 3"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {data && (
        <p className="mt-2 text-xs text-muted-foreground">
          Naive straight-line projection based on average monthly net cash flow -- not a
          real forecast model.
        </p>
      )}
    </AnalyticsCard>
  );
}
