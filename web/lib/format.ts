const currencyFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

export function formatCurrency(value: string | number): string {
  const numeric = typeof value === "string" ? Number.parseFloat(value) : value;
  return currencyFormatter.format(Number.isFinite(numeric) ? numeric : 0);
}

export function formatDate(value: string): string {
  return new Date(value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}
