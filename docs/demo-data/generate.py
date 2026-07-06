"""Regenerates the demo CSVs in this directory with 6 months of realistic,
date-relative transaction history (recurring salary/rent/utilities/gym,
weekly groceries, occasional Uber/Amazon/dining, and Netflix/Spotify
subscriptions on the credit card) ending at today. Re-run any time to refresh
the dates: `python docs/demo-data/generate.py`.

Amounts and merchant names are deliberately chosen against the app's known
rules: "Whole Foods"/"Netflix"/"Spotify"/"Uber"/"Starbucks"/"Amazon" are
recognized by app/ingestion/normalization/merchant_normalizer.py and get
auto-categorized; the gym/Netflix/Spotify charges are fixed-amount and
regularly spaced so app/analytics/modules/subscriptions.py detects them,
while grocery/coffee amounts are randomized past its 10% tolerance so they
are correctly *not* flagged as subscriptions.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

OUT_DIR = Path(__file__).parent
SEED = 42


def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def main() -> None:
    rng = random.Random(SEED)
    today = date.today()
    this_month_start = today.replace(day=1)
    months = [add_months(this_month_start, -i) for i in range(5, -1, -1)]  # oldest first

    checking_rows: list[tuple[date, str, str]] = []
    credit_card_rows: list[tuple[date, str, str]] = []

    for i, month_start in enumerate(months):

        def d(day: int) -> date:
            return month_start.replace(day=day)

        def include(candidate: date) -> bool:
            return candidate <= today

        # --- Checking ---
        if include(d(1)):
            checking_rows.append((d(1), "ACME CORP PAYROLL DIRECT DEP", "6200.00"))
        if include(d(3)):
            checking_rows.append((d(3), "GREENFIELD APARTMENTS LLC", "-1850.00"))
        if include(d(9)):
            checking_rows.append(
                (d(9), "CITY POWER AND WATER UTIL", f"-{rng.uniform(110, 150):.2f}")
            )
        if include(d(12)):
            checking_rows.append((d(12), "IRONWORKS FITNESS MEMBERSHIP", "-45.00"))
        for day in (6, 13, 20, 27):
            if include(d(day)):
                checking_rows.append(
                    (d(day), f"WHOLEFDS MKT #{1000 + day}", f"-{rng.uniform(80, 130):.2f}")
                )
        for _ in range(2):
            day = rng.randint(2, 27)
            if include(d(day)):
                checking_rows.append(
                    (d(day), "UBER TRIP HELP.UBER.COM", f"-{rng.uniform(15, 35):.2f}")
                )
        for day in (2, 16, 23):
            if include(d(day)):
                checking_rows.append(
                    (d(day), f"STARBUCKS STORE #{2200 + day}", f"-{rng.uniform(4.5, 8.5):.2f}")
                )
        if i == 2 and include(d(22)):
            checking_rows.append((d(22), "AUTO REPAIR SHOP", "-540.00"))

        # --- Credit card ---
        month_charges: list[tuple[date, str, str]] = []
        if include(d(5)):
            month_charges.append((d(5), "NETFLIX.COM", "15.99"))
        if include(d(8)):
            month_charges.append((d(8), "SPOTIFY USA", "10.99"))
        for _ in range(rng.randint(1, 2)):
            day = rng.randint(10, 18)
            if include(d(day)):
                month_charges.append(
                    (d(day), f"AMAZON.COM*{rng.randint(100000, 999999)}", f"{rng.uniform(25, 150):.2f}")
                )
        if rng.random() < 0.7:
            day = rng.randint(10, 19)
            if include(d(day)):
                month_charges.append((d(day), "THE CORNER BISTRO", f"{rng.uniform(35, 80):.2f}"))

        credit_card_rows.extend(month_charges)

        # Pay down slightly more than this month's charges (skip month 0 --
        # nothing to pay off yet), showing a healthy "on track" trend.
        total_charges = sum(float(amount) for _, _, amount in month_charges)
        if i > 0 and total_charges > 0 and include(d(25)):
            # 1.35x (not just 1.15x) so the trailing-window average paydown
            # comes out clearly positive even after month 0's charges (which
            # are deliberately left unpaid, to simulate a pre-existing
            # starting balance) -- see docs/demo-data/README.md.
            payment = round(total_charges * 1.35, 2)
            credit_card_rows.append((d(25), "PAYMENT RECEIVED - THANK YOU", f"-{payment:.2f}"))
            if include(d(25)):
                checking_rows.append((d(25), "PAYMENT TO CREDIT CARD", f"-{payment:.2f}"))

    def write_csv(path: Path, rows: list[tuple[date, str, str]]) -> None:
        rows_sorted = sorted(rows, key=lambda r: r[0])
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Description", "Amount"])
            for posted_at, description, amount in rows_sorted:
                writer.writerow([posted_at.isoformat(), description, amount])

    write_csv(OUT_DIR / "checking.csv", checking_rows)
    write_csv(OUT_DIR / "credit_card.csv", credit_card_rows)
    print(f"Wrote {len(checking_rows)} checking rows, {len(credit_card_rows)} credit card rows.")


if __name__ == "__main__":
    main()
