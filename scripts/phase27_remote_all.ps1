# Phase 27 second-laptop block, fully automatic: self-check -> run -> push. No AI tool needed.
#
#   powershell -ExecutionPolicy Bypass -File scripts\phase27_remote_all.ps1 -Name "Your Name" -Email "you@example.com"
#
# Safe to start again after any interruption: a passed self-check is remembered and finished episodes are skipped.
param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Email,
    [int]$Workers = 4
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# Keep Windows from idle-sleeping while this script runs (no settings are changed; it ends with the script).
# A closed lid or choosing Sleep still sleeps the laptop.
Add-Type -Namespace Sentinel -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
[void][Sentinel.Power]::SetThreadExecutionState([uint32]"0x80000001")  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
$env:HF_HUB_OFFLINE = "1"
$py = ".venv\Scripts\python.exe"
$result = "data\eval_results\phase27\runs\B_v4-stress-dt2-v1.jsonl"
$marker = "data\eval_results\phase27\.canary_pass"
$want = 20

function Done-Count {
    if (-not (Test-Path $result)) { return 0 }
    $seeds = @{}
    foreach ($line in Get-Content $result) {
        if ($line.Trim()) { $seeds[($line | ConvertFrom-Json).seed] = $true }
    }
    return $seeds.Count
}

if (-not (Test-Path $py)) { throw "No .venv found. Do step 2 of scripts\PHASE27_REMOTE_RUN.md first." }

# 1. Self-check (once)
if (-not (Test-Path $marker)) {
    Write-Host "== Step 1/3: self-check (10-25 minutes) =="
    & $py scripts\phase27_canary.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "CANARY FAIL - stopping. Send a screenshot of the lines above to Manoj." -ForegroundColor Red
        exit 1
    }
    Set-Content $marker "passed $(Get-Date -Format s)"
} else {
    Write-Host "== Step 1/3: self-check already passed =="
}

# 2. Run the block; retry a few times if the run stops early
Write-Host "== Step 2/3: running 20 episodes (about 5-7 hours). Leave this window open. =="
for ($attempt = 1; $attempt -le 3 -and (Done-Count) -lt $want; $attempt++) {
    & $py scripts\phase27_run.py --system B --regime v4-stress-dt2-v1 --seeds 1050040-1050059 --workers $Workers
    Write-Host "finished episodes: $(Done-Count) of $want"
}
if ((Done-Count) -lt $want) {
    Write-Host "Only $(Done-Count) of $want episodes finished. Start this script again later; nothing is lost." -ForegroundColor Yellow
    exit 1
}

# 3. Push only the result file to its own branch (git prints progress on stderr: do not treat it as an error)
$ErrorActionPreference = "Continue"
Write-Host "== Step 3/3: pushing the result to GitHub =="
git config user.name $Name
git config user.email $Email
$branch = git rev-parse --abbrev-ref HEAD
if ($branch -ne "m27-runs-remote") { git checkout -B m27-runs-remote }
git add -- $result
git commit -m "Phase 27: B stress seeds 1050040-1050059 (second laptop)"
for ($try = 1; $try -le 4; $try++) {
    git push -u origin m27-runs-remote
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds (15 * $try)
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "Push failed (no internet?). Run this script again when online; it will only retry the push." -ForegroundColor Yellow
    exit 1
}
Write-Host "ALL DONE - tell Manoj 'pushed'." -ForegroundColor Green
