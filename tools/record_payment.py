#!/usr/bin/env python3
"""
Record a payment on the 309 McClure note.

This is the ONLY supported way to change ledger.json. It validates everything,
keeps `confirmedThrough` honest, and refuses to record a payment out of order.

Examples
--------
  # Josh paid $450 on time -- the normal month
  python tools/record_payment.py

  # He paid late
  python tools/record_payment.py --received 2026-10-14 --note late

  # He paid short
  python tools/record_payment.py --amount 200 --received 2026-11-01 --note partial

  # He missed it entirely
  python tools/record_payment.py --amount 0 --note missed

  # He sent extra (goes to principal)
  python tools/record_payment.py --amount 1200 --note "catch-up + extra principal"

  # Fix a payment already recorded (does NOT advance confirmedThrough)
  python tools/record_payment.py --amend 3 --amount 450 --received 2026-10-14 --note late

  # See what would happen, change nothing
  python tools/record_payment.py --dry-run
"""

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.normpath(os.path.join(HERE, "..", "ledger.json"))


def add_months(d: dt.date, months: int) -> dt.date:
    y, m = divmod(d.year * 12 + (d.month - 1) + months, 12)
    m += 1
    # every due date is the 1st, but be safe if that ever changes
    last = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]
    return dt.date(y, m, min(d.day, last))


def parse_date(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        sys.exit(f"ERROR: '{s}' is not a date. Use YYYY-MM-DD (e.g. 2026-10-14).")


def main() -> None:
    p = argparse.ArgumentParser(description="Record a payment on the 309 McClure note.")
    p.add_argument("--amount", type=float, default=None,
                   help="Dollars actually received. 0 = missed. Default: the scheduled payment.")
    p.add_argument("--received", type=str, default=None,
                   help="Date received, YYYY-MM-DD. Default: the due date.")
    p.add_argument("--note", type=str, default="",
                   help='Free text shown on the row, e.g. "late", "partial", "extra principal".')
    p.add_argument("--amend", type=int, default=None, metavar="N",
                   help="Correct an ALREADY-recorded payment N. Does not advance confirmedThrough.")
    p.add_argument("--dry-run", action="store_true", help="Show the change, write nothing.")
    p.add_argument("--as-of", type=str, default=None, help="Override today's date (CI use).")
    args = p.parse_args()

    with open(LEDGER, encoding="utf-8") as fh:
        L = json.load(fh)

    note = L["note"]
    ct = int(L.get("confirmedThrough", 0))
    term = int(note["termMonths"])
    sched = float(note["monthlyPayment"])
    first = parse_date(note["firstPaymentDate"])

    amending = args.amend is not None
    n = args.amend if amending else ct + 1

    # ---- validate ------------------------------------------------------
    if n < 1 or n > term:
        sys.exit(f"ERROR: payment #{n} is outside the {term}-payment schedule.")
    if amending and n > ct:
        sys.exit(f"ERROR: payment #{n} has not been recorded yet (confirmedThrough={ct}). "
                 f"Record it normally instead of using --amend.")
    if not amending and ct >= term:
        sys.exit("ERROR: all 60 payments are already recorded. The loan is paid off.")

    due = add_months(first, n - 1)
    amount = sched if args.amount is None else float(args.amount)
    received = due if args.received is None else parse_date(args.received)
    today = parse_date(args.as_of) if args.as_of else dt.date.today()

    if amount < 0:
        sys.exit("ERROR: amount cannot be negative.")
    if amount == 0 and args.received:
        sys.exit("ERROR: a missed payment ($0) has no received date. Drop --received.")

    if amount > 0:
        # Money that hasn't landed cannot be inside confirmedThrough.
        if received > today:
            sys.exit(f"ERROR: received date {received} is in the future (today is {today}). "
                     "confirmedThrough must only ever cover money that has ACTUALLY landed.")
        if received < due:
            print(f"  note: paid {(due - received).days} day(s) EARLY (due {due}).")
    else:
        # You cannot call a payment "missed" before it was ever due.
        if due > today:
            sys.exit(f"ERROR: payment #{n} isn't due until {due} (today is {today}). "
                     "Nothing to record yet.")

    # ---- build the entry ----------------------------------------------
    clean = (abs(amount - sched) < 0.005) and (received == due) and not args.note.strip()

    exceptions = [e for e in L.get("exceptions", []) if int(e["n"]) != n]
    if not clean:
        entry = {"n": n, "amount": round(amount, 2)}
        if amount > 0 and received != due:
            entry["receivedOn"] = received.isoformat()
        if args.note.strip():
            entry["note"] = args.note.strip()
        exceptions.append(entry)
    exceptions.sort(key=lambda e: int(e["n"]))

    new_ct = ct if amending else n

    # ---- report --------------------------------------------------------
    days_late = (received - due).days if amount > 0 else 0
    if amount == 0:
        status = "MISSED"
    elif amount + 0.005 < sched:
        status = "PARTIAL"
    elif days_late > 0:
        status = f"LATE ({days_late}d)"
    elif amount - 0.005 > sched:
        status = "EXTRA PRINCIPAL"
    else:
        status = "PAID ON TIME"

    verb = "AMEND" if amending else "RECORD"
    print(f"\n  {verb} payment #{n}   due {due}")
    print(f"  amount    ${amount:,.2f}   (scheduled ${sched:,.2f})")
    print(f"  received  {received if amount > 0 else '-- nothing received --'}")
    print(f"  status    {status}")
    if args.note.strip():
        print(f"  note      {args.note.strip()}")
    print(f"  confirmedThrough  {ct} -> {new_ct}")
    if days_late > int(note.get("lateFeeGraceDays", 10)):
        fee = round(amount * float(note.get("lateFeeRate", 0.05)), 2)
        print(f"\n  ! {days_late} days late. The note allows a ${fee:,.2f} late fee "
              f"({note['lateFeeRate']:.0%} after {note['lateFeeGraceDays']} days).")
        print("    It is NOT applied automatically. Charging it is your call.")
    if status == "MISSED":
        print("\n  ! Missed payment. Unpaid interest carries to next month; principal does not drop.")
        print("    The note carries an 18% default rate and the mortgage has a confession of judgment.")

    if args.dry_run:
        print("\n  --dry-run: nothing written.\n")
        return

    L["exceptions"] = exceptions
    L["confirmedThrough"] = new_ct
    L["asOf"] = today.isoformat()

    with open(LEDGER, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(L, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"\n  wrote {LEDGER}")
    print(f"  commit + push, then check https://saltybayflips-ai-empire.github.io/mcclure-note-ledger/\n")


if __name__ == "__main__":
    main()
