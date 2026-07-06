"use client";

import { Banknote, Landmark, LineChart, PiggyBank, Sparkles } from "lucide-react";

import { CreateAccountDialog } from "@/components/accounts/create-account-dialog";
import { NetWorthTile } from "@/components/dashboard/net-worth-tile";
import { ImportCsvDialog } from "@/components/transactions/import-csv-dialog";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";

const ROADMAP = [
  { title: "Cash flow", icon: LineChart },
  { title: "Investments", icon: Landmark },
  { title: "Budget tracking", icon: PiggyBank },
  { title: "AI insights", icon: Sparkles },
];

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

      <section>
        <div className="mb-3 flex items-center gap-2">
          <Banknote className="size-4 text-muted-foreground" />
          <h2 className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
            Coming next
          </h2>
        </div>
        <div className="grid gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-4">
          {ROADMAP.map(({ title, icon: Icon }) => (
            <div
              key={title}
              className="flex items-center gap-3 bg-card px-4 py-3.5 text-sm text-muted-foreground"
            >
              <Icon className="size-4 shrink-0" />
              {title}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
