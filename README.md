# 309 McClure St — Private Note Ledger

A free, self-hosted payment record for the private promissory note on **309 McClure St, Tallulah, LA 71282**.

**Lender:** Khalil Giawashi · **Borrower:** Unilateral, LLC (guaranteed by Joshua Shane Farris)
**Note:** $20,229.77 @ 12% fixed · 60 × $450.00/mo · first payment 8/1/2026 · matures 7/1/2031
**Secured by:** first-position mortgage, Madison Parish LA — Inst. #149571, Book 474 / Page 919, recorded 6/29/2026

**Live page:** https://saltybayflips-ai-empire.github.io/mcclure-note-ledger/

Both lender and borrower can view the running balance, the full payment ledger, per-year interest totals, and download a **statement (PDF)** or the **full ledger (CSV)**.

---

## Why this exists

The alternative was a third-party loan servicer (~$1,265 over the life of the loan). This does the same recordkeeping for $0. What it does **not** do: it does not pull the payment (the borrower pushes it), and it does not file anyone's tax forms.

**The trust mechanism is git.** Every edit to `ledger.json` is a commit — timestamped, attributed, and permanent. Neither party can silently rewrite history. The page links directly to the change log.

---

## Who can change this

**Only the lender.** Write access is limited to `khailgio` and the `saltybayflips-AI-Empire` org account. The borrower — and the rest of the internet — can **read** the page and nothing more. That is enforced by GitHub, not by trust.

Anyone can fork the repo or open an issue. Neither changes the ledger: a pull request is a *proposal* that only the lender can merge. **Issues are left open on purpose** — they give the borrower a public, timestamped way to dispute an entry, which makes the record stronger, not weaker.

---

## How to record a payment — three ways

All three run the same validation and produce the same one-line commit. Pick whichever is in front of you.

### 1. From your computer (easiest)

```powershell
cd C:\Users\khali\Projects\mcclure-note-ledger
.\Record-Payment.ps1
```

It pulls the latest, asks what happened, shows you the diff, and publishes on your OK. Non-interactive versions:

```powershell
.\Record-Payment.ps1 -Yes                                             # paid $450 on time
.\Record-Payment.ps1 -Amount 450 -Received 2026-10-14 -Note late -Yes # late
.\Record-Payment.ps1 -Amount 200 -Received 2026-11-01 -Note partial -Yes
.\Record-Payment.ps1 -Amount 0 -Note missed -Yes
.\Record-Payment.ps1 -Amend 3 -Amount 450 -Received 2026-10-14 -Yes   # fix a past entry
.\Record-Payment.ps1 -DryRun                                          # preview, change nothing
```

### 2. From your phone

**GitHub → Actions → "Record payment" → Run workflow.** Fill in the boxes (all optional — blank means "the scheduled $450, on the due date") and press the green button. Only collaborators see that button. Tick **dry run** to preview first.

### 3. By hand

Edit [`ledger.json`](https://github.com/saltybayflips-AI-Empire/mcclure-note-ledger/blob/main/ledger.json) → pencil icon → **Commit changes**. See the format below. The script exists so you don't have to do this, but nothing stops you.

The live page updates within a minute or two.

### Normal month — payment landed on time

Bump `confirmedThrough` by one, and update `asOf`:

```json
"confirmedThrough": 3,
"asOf": "2026-10-02"
```

That's it. Payments 1–3 now show as **Paid**, $450.00 each, on their due dates. Payment 4 onward shows as **Scheduled** — the page never claims money arrived that you haven't actually seen.

### Something was different — record an exception

Add an entry to `exceptions` for that payment number. Still bump `confirmedThrough` to cover it.

```json
"confirmedThrough": 5,
"exceptions": [
  { "n": 3, "amount": 450.00, "receivedOn": "2026-10-14", "note": "late" },
  { "n": 4, "amount": 200.00, "receivedOn": "2026-11-01", "note": "partial" },
  { "n": 5, "amount": 0,      "note": "missed" }
],
"asOf": "2026-12-03"
```

| Field | Meaning |
|---|---|
| `n` | Payment number, 1–60 |
| `amount` | Dollars actually received. `0` = missed. More than 450 = extra principal. |
| `receivedOn` | `YYYY-MM-DD`. Omit if it arrived on the due date. |
| `note` | Free text shown next to the row. |

The amortization is **recalculated from the actual amounts and dates**, so a short or late payment correctly changes the interest/principal split of every payment after it. Unpaid interest carries forward rather than being folded into principal.

### Rules

- **Only bump `confirmedThrough` once the money is actually in the Tyndall account.** It is the line between *record* and *projection*.
- **Never edit the `note` block** (the loan terms). Those come from the executed note and the recorded mortgage. A change there would show up loudly in the commit diff — which is the point.
- Late fees (5% after 10 days) and the 18% default rate are displayed for reference and are **never auto-applied** to the balance. Charging them is the lender's call.

---

## Tax notes (lender)

- Only the **interest** column is taxable income — reported as ordinary interest income (Form 1040 line 2b; Schedule B Part I once taxable interest exceeds $1,500/yr). Principal received is a **return of capital**, not income.
- **Unilateral, LLC must issue a Form 1099-INT** for any year it pays $600 or more of interest in the course of its business. The lender files nothing (Form 1098 is filed by the recipient, and only when the payer is an *individual* — here the payer is an LLC).
- The **$232.75** of odd-days interest collected at closing and refunded to the lender is **taxable interest income in the year received (2026)** — it is not a return of capital. It is included in the 2026 totals and shown separately on the statement.
- If the borrower ever pays late, short, or early, the interest/principal split changes — **use this ledger's numbers, not the original amortization schedule.**

Nothing about this loan belongs in Stessa. It is a personal note receivable, not rental income.

---

## What's in here

| File | Purpose |
|---|---|
| `ledger.json` | The only data file: note terms, `confirmedThrough`, and exceptions. |
| `index.html` | The whole app. Self-contained — no frameworks, no CDN, no tracking, works offline. |
| `Record-Payment.ps1` | Record a payment from your computer: pull → validate → diff → commit → push. |
| `tools/record_payment.py` | The validation + write logic. Used by the script and the phone button alike. |
| `.github/workflows/record-payment.yml` | The phone button (Actions → Record payment). Collaborators only. |
| `robots.txt` | Asks search engines not to index the page. |

### What the recorder refuses to do

- **Record a payment dated in the future.** `confirmedThrough` may only ever cover money that has actually landed.
- **Skip a payment.** Payments record in order; use `--amend N` to correct one already recorded.
- **Amend a payment that was never recorded**, or record past payment #60.
- **Accept a negative amount**, or a received-date on a $0 (missed) payment.

It also *tells* you, without acting: how many days late a payment was and what the note's 5% late fee would come to, and — on a missed payment — that unpaid interest carries forward and the note carries an 18% default rate. **Late fees and default interest are never applied automatically.** Charging them is the lender's call.

Not indexed by search engines, but the repository is **public** — anyone with the URL can read it. No Social Security numbers, bank account numbers, or routing numbers ever go in this repo. (The loan amount, rate, parties, and lien are already public record at the Madison Parish Clerk of Court.)

---

*This page is a payment record. It is not a tax document and not legal advice. The controlling documents are the executed promissory note and the recorded mortgage.*
