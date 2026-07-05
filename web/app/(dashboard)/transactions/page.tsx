import { CreateAccountDialog } from "@/components/accounts/create-account-dialog";
import { ImportCsvDialog } from "@/components/transactions/import-csv-dialog";
import { TransactionsTable } from "@/components/transactions/transactions-table";

export default function TransactionsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Transactions</h1>
          <p className="text-sm text-muted-foreground">
            Every transaction across every connected account.
          </p>
        </div>
        <div className="flex gap-2">
          <CreateAccountDialog />
          <ImportCsvDialog />
        </div>
      </div>

      <TransactionsTable />
    </div>
  );
}
