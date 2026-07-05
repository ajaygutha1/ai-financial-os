import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NetWorthTile } from "@/components/dashboard/net-worth-tile";

function ComingSoonCard({ title }: { title: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">Coming in a later milestone.</p>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Your complete financial picture, in one place.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <NetWorthTile />
        <ComingSoonCard title="Cash Flow" />
        <ComingSoonCard title="Investments" />
        <ComingSoonCard title="Budget Tracking" />
        <ComingSoonCard title="AI Insights" />
        <ComingSoonCard title="Upcoming Bills" />
      </div>
    </div>
  );
}
