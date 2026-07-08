<#
.SYNOPSIS
  Record a payment on the 309 McClure note and publish it.

.DESCRIPTION
  Pulls the latest ledger, records the payment, shows you exactly what changed,
  then commits and pushes. The live page updates about a minute later.

  Only you (khailgio) and the Salty Bay Flips org account can push. Josh can
  read the page and open an issue if he disputes something; he cannot edit it.

.EXAMPLE
  .\Record-Payment.ps1
  Josh paid $450 on time. Walks you through it with prompts.

.EXAMPLE
  .\Record-Payment.ps1 -Amount 450 -Received 2026-10-14 -Note late -Yes

.EXAMPLE
  .\Record-Payment.ps1 -Amount 0 -Note missed -Yes

.EXAMPLE
  .\Record-Payment.ps1 -Amend 3 -Amount 450 -Received 2026-10-14 -Note late -Yes
  Fix a payment you already recorded. Does not advance confirmedThrough.

.EXAMPLE
  .\Record-Payment.ps1 -DryRun
  See what would happen. Changes nothing.
#>
[CmdletBinding()]
param(
  [double] $Amount,
  [string] $Received,
  [string] $Note = "",
  [int]    $Amend,
  [switch] $DryRun,
  [switch] $Yes
)

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot
$live = 'https://saltybayflips-ai-empire.github.io/mcclure-note-ledger/'

function Fail($msg) { Write-Host ""; Write-Host "  $msg" -ForegroundColor Red; Write-Host ""; exit 1 }

# --- sanity ------------------------------------------------------------
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { Fail "python isn't on PATH." }
if (-not (Test-Path (Join-Path $repo 'ledger.json')))        { Fail "ledger.json not found in $repo" }

$branch = (git -C $repo rev-parse --abbrev-ref HEAD)
if ($branch -ne 'main') { Fail "You're on branch '$branch', not main. Switch to main first." }

$dirty = git -C $repo status --porcelain -- ledger.json
if ($dirty) { Fail "ledger.json already has uncommitted changes. Commit or discard them first." }

# --- get the latest before touching anything ---------------------------
Write-Host "`n  Pulling latest..." -ForegroundColor DarkGray
git -C $repo pull --rebase --quiet origin main
if ($LASTEXITCODE -ne 0) { Fail "git pull failed. Resolve that first." }

# --- what are we recording? --------------------------------------------
$ledger = Get-Content (Join-Path $repo 'ledger.json') -Raw | ConvertFrom-Json
$next   = [int]$ledger.confirmedThrough + 1
$sched  = [double]$ledger.note.monthlyPayment

$interactive = -not ($PSBoundParameters.ContainsKey('Amount') -or $PSBoundParameters.ContainsKey('Amend'))

if ($interactive) {
  Write-Host ""
  Write-Host "  Recording payment #$next on the 309 McClure note." -ForegroundColor Cyan
  Write-Host "  Scheduled: `$$('{0:N2}' -f $sched). Press Enter to accept the default in [brackets]."
  Write-Host ""

  $a = Read-Host "  Amount received [$('{0:N2}' -f $sched)]  (0 = missed)"
  if ([string]::IsNullOrWhiteSpace($a)) { $Amount = $sched } else { $Amount = [double]$a }

  if ($Amount -gt 0) {
    $r = Read-Host "  Date received YYYY-MM-DD [on the due date]"
    if (-not [string]::IsNullOrWhiteSpace($r)) { $Received = $r }
  }

  $n = Read-Host "  Note, if anything was unusual [none]"
  if (-not [string]::IsNullOrWhiteSpace($n)) { $Note = $n }
}

# --- build the python call ---------------------------------------------
$py = @('tools/record_payment.py')
if ($PSBoundParameters.ContainsKey('Amend')) { $py += @('--amend', $Amend) }
if ($null -ne $Amount -and ($PSBoundParameters.ContainsKey('Amount') -or $interactive)) { $py += @('--amount', $Amount) }
if ($Received) { $py += @('--received', $Received) }
if ($Note)     { $py += @('--note', $Note) }
if ($DryRun)   { $py += '--dry-run' }

Push-Location $repo
try {
  python @py
  if ($LASTEXITCODE -ne 0) { Fail "Nothing was recorded." }
  if ($DryRun) { exit 0 }

  # --- show exactly what changed ---------------------------------------
  Write-Host "  Diff:" -ForegroundColor DarkGray
  git -C $repo --no-pager diff --unified=0 -- ledger.json | Select-String '^[+-][^+-]' | ForEach-Object {
    $line = $_.Line
    if ($line.StartsWith('+')) { Write-Host "    $line" -ForegroundColor Green }
    else                       { Write-Host "    $line" -ForegroundColor Red }
  }
  Write-Host ""

  if (-not $Yes) {
    $ok = Read-Host "  Publish this? (y/N)"
    if ($ok -notmatch '^[Yy]') {
      git -C $repo checkout -- ledger.json
      Write-Host "`n  Reverted. Nothing published.`n" -ForegroundColor Yellow
      exit 0
    }
  }

  # --- publish ----------------------------------------------------------
  $ledger2 = Get-Content (Join-Path $repo 'ledger.json') -Raw | ConvertFrom-Json
  $msg = "Record payment #$($ledger2.confirmedThrough) (as of $($ledger2.asOf))"

  git -C $repo add ledger.json
  git -C $repo -c user.name="Khalil Giawashi" -c user.email="khalilgio@gmail.com" commit -q -m $msg
  if ($LASTEXITCODE -ne 0) { Fail "commit failed" }

  git -C $repo push -q origin main
  if ($LASTEXITCODE -ne 0) { Fail "push failed. If it says 'repository not found', that's an ACCESS gap, not a missing repo -- see CLAUDE.md section 9." }

  Write-Host "  Published." -ForegroundColor Green
  Write-Host "  $live  (live in ~1 min)`n"
}
finally { Pop-Location }
