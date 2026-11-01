# Laya: the local decision model for Phase 4

Archway asks typed questions (yes/no, small choices) about each researched
component. With no Jev account, they are answered by **Laya**, an open-source
"System One" decision model (Apache-2.0) that runs on this Mac and serves the
same `/v1/systemone` protocol as Jev. Results are labelled `laya/...`, never Jev.

It lives in its own environment (PyTorch is large) so the backend stays small.

## Start it (from `backend/`)

```bash
./services/laya/run.sh
```

The first start downloads its checkpoints (about 1 GB, into `~/.cache/huggingface`).
It listens on `http://127.0.0.1:8100` and uses the Mac's GPU (MPS).
Health check: `curl http://127.0.0.1:8100/health`.

## Settings (backend/.env)

```
JEV_MODE=live
DECISION_PROVIDER=laya
DECISION_URL=http://127.0.0.1:8100
DECISION_MODEL=typed-decisions
```

If Laya is not running, research still finishes: every decision is recorded
as "not evaluated" with a note saying how to start it, and the eligibility
gate decides from its rules alone.

## How good is it (measured 2026-10-16, 14 labelled Archway questions)

| Question style | Laya `typed-decisions` | Chat router (OpenRouter `typesafe/jev-router`) |
|---|---|---|
| Four-step score ("does not meet" ... "clearly meets") | 7 / 14 (chance) | 14 / 14 |
| Yes / no ("this component provides X") | **13 / 14**, 44 ms | 14 / 14, 2.4 s |

So Archway asks Laya short yes/no questions. Its probabilities are not
calibrated (clear "yes" answers sat at 0.52 to 0.67), so answers between 0.30
and 0.50 are flagged for human review.

## Install (already done once)

```bash
python3 -m venv services/laya/.venv.nosync
services/laya/.venv.nosync/bin/python -m pip install "laya[serve]==0.4.8"
```
