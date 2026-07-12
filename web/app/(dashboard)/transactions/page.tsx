import { CreateAccountDialog } from "@/components/accounts/create-account-dialog";
import { ImportCsvDialog } from "@/components/transactions/import-csv-dialog";
import { TransactionsTable } from "@/components/transactions/transactions-table";

export default function TransactionsPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6 md:px-10">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-heading text-3xl">Transactions</h1>
          <p className="mt-1 text-sm text-muted-foreground">
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
