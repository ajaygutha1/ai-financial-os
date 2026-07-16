"use client";

import { CreateAccountDialog } from "@/components/accounts/create-account-dialog";
import { AIInsightsCard } from "@/components/dashboard/ai-insights-card";
import { AllocationTile } from "@/components/dashboard/allocation-tile";
import { BudgetCard } from "@/components/dashboard/budget-card";
import { CashFlowChart } from "@/components/dashboard/cash-flow-chart";
import { DebtPayoffCard } from "@/components/dashboard/debt-payoff-card";
import { EmergencyFundTile } from "@/components/dashboard/emergency-fund-tile";
import { ExpenseTrendsCard } from "@/components/dashboard/expense-trends-card";
import { FinancialRatiosTile } from "@/components/dashboard/financial-ratios-tile";
import { ForecastChart } from "@/components/dashboard/forecast-chart";
import { GoalsCard } from "@/components/dashboard/goals-card";
import { NetWorthTile } from "@/components/dashboard/net-worth-tile";
import { SubscriptionsCard } from "@/components/dashboard/subscriptions-card";
import { UpcomingBillsCard } from "@/components/dashboard/upcoming-bills-card";
import { ImportCsvDialog } from "@/components/transactions/import-csv-dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export default function DashboardPage() {
  const { user } = useAuth();
  const firstName = user?.full_name?.trim().split(/\s+/)[0];

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-6 md:px-10">
      <div>
        <h1 className="font-heading text-3xl">
          {greeting()}
          {firstName ? `, ${firstName}` : ""}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Here&apos;s where things stand — and what to do next.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <NetWorthTile className="lg:col-span-2" />

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Get started
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2.5">
            <p className="text-sm text-muted-foreground">
              Connect an account and bring in your history to see your full picture.
            </p>
            <div className="flex flex-col gap-2 pt-1 sm:flex-row lg:flex-col">
              <CreateAccountDialog />
              <ImportCsvDialog />
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <CashFlowChart className="lg:col-span-2" />
        <EmergencyFundTile />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <FinancialRatiosTile />
        <ExpenseTrendsCard />
        <SubscriptionsCard />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <DebtPayoffCard className="lg:col-span-2" />
        <AIInsightsCard />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <AllocationTile />
        <ForecastChart />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <GoalsCard />
        <BudgetCard />
        <UpcomingBillsCard />
      </div>
    </div>
  );
}
