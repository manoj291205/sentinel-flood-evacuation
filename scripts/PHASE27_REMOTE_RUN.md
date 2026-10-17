# Phase 27 — running one block on a second laptop (no lead session needed)

**Confidential.** This repository is private and the invention is not yet filed. Do not share the code,
copy it elsewhere, or talk about what it does.

Your job: run **20 simulation episodes** (Baseline B, stress regime, seeds 1050040–1050059) and push the
result file to GitHub. You do not edit any code. Expected time: about 30–45 minutes of setup, a 10–25 minute
self-check, then about **5–7 hours** of unattended running.

---

## 0. Before you start (once)
1. Accept the GitHub invitation to `iamnoob96/sentinel-sprint` (email from GitHub, or github.com → notifications).
2. Install **Git for Windows**: https://git-scm.com/download/win (all defaults).
3. Install **Python 3.12** (64-bit) from https://www.python.org/downloads/windows/ — pick the newest
   "Python 3.12.x" Windows installer. Tick **"Add python.exe to PATH"**. Python 3.13/3.14 is **not** OK.
4. Plug the laptop in and leave the **lid open**. The script keeps Windows awake by itself while it runs
   (no settings are changed), but closing the lid or choosing Sleep still stops it.
5. Close Chrome, games and other heavy apps while it runs (it needs about 4–6 GB of free RAM).

## 1. Get the code (PowerShell)
Open **PowerShell** (Start → type PowerShell) and paste one line at a time:
```powershell
cd $HOME\Documents
git clone -c core.autocrlf=false https://github.com/iamnoob96/sentinel-sprint.git
cd sentinel-sprint
git checkout m27-eval
```
A browser window may open to sign in to GitHub the first time — sign in with the invited account.

## 2. Create the Python environment (about 5 minutes)
```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install numpy==2.5.4 scipy==1.18.1 networkx==3.6.1
```
Only these three packages are needed. Do **not** install `requirements.txt`.

## 3. Start the automatic run (one command, then leave it)
In the same PowerShell window, inside the `sentinel-sprint` folder (use your own name and email):
```powershell
powershell -ExecutionPolicy Bypass -File scripts\phase27_remote_all.ps1 -Name "Your Name" -Email "you@example.com"
```
It does everything by itself, in three steps. **Wait until step 2 has started (about 10–25 minutes, the
self-check must print `CANARY PASS`), then you can leave it overnight**:
1. **Self-check (10–25 min):** re-runs five episodes already finished on the main laptop and compares every
   number. On `CANARY FAIL` it stops: send Manoj a screenshot and do nothing else.
2. **Run (5–7 hours):** 20 episodes, one line each, e.g. `B v4-stress-dt2-v1 1050043 OK 3120.5`. The first line
   appears after roughly 30–90 minutes; that is normal. The fan will be loud; that is expected.
3. **Push:** sends only the result file to the branch `m27-runs-remote`, then prints **`ALL DONE`**.
   Tell Manoj "pushed".

**If anything interrupts it** (restart, sleep, window closed, no internet at the end): open PowerShell,
`cd $HOME\Documents\sentinel-sprint`, and run the same command again. The passed self-check is remembered,
finished episodes are skipped, and a failed push is retried.

Check progress from a second PowerShell window inside the folder (finished when it prints 20):
```powershell
(Get-Content data\eval_results\phase27\runs\B_v4-stress-dt2-v1.jsonl).Count
```

## 4. Manual fallback (only if Manoj asks)
```powershell
$env:HF_HUB_OFFLINE = "1"
.venv\Scripts\python scripts\phase27_canary.py
.venv\Scripts\python scripts\phase27_run.py --system B --regime v4-stress-dt2-v1 --seeds 1050040-1050059 --workers 4
git checkout -b m27-runs-remote
git add data/eval_results/phase27/runs/B_v4-stress-dt2-v1.jsonl
git commit -m "Phase 27: B stress seeds 1050040-1050059 (second laptop)"
git push -u origin m27-runs-remote
```

## Do not
- Edit any file, run other systems or seeds, or run `phase27_analyze.py`.
- Install `requirements.txt` or upgrade numpy / scipy / networkx.
- Delete or rename the result file.

After Manoj confirms the file arrived, you can delete the `sentinel-sprint` folder.
