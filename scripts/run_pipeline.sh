#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_pipeline.sh — run the full Oru Kural data pipeline locally, step by step
#
# Usage:
#   cd scripts/
#   bash run_pipeline.sh             # full pipeline
#   bash run_pipeline.sh --dry-run   # skip X API, use local JSON instead
#   bash run_pipeline.sh --from categorize_signals   # resume from a step
#   bash run_pipeline.sh --only scrape_grievances    # run a single step
#
# Flags:
#   --dry-run              passes --dry-run to scrape_tweets.py (no X API call)
#   --from <script_name>   skip all steps before <script_name>
#   --only <script_name>   run just that one step
#   --skip-gemini          skip steps that call Gemini (categorize/cluster/link/events)
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$SCRIPT_DIR/.venv"

# ── colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; RESET='\033[0m'
BOLD='\033[1m'

info()    { echo -e "${GREEN}[pipeline]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[pipeline]${RESET} $*"; }
step()    { echo -e "\n${BOLD}━━━ $* ━━━${RESET}"; }
err()     { echo -e "${RED}[pipeline] ERROR:${RESET} $*" >&2; }

# ── flags ─────────────────────────────────────────────────────────────────────
DRY_RUN=0
FROM_STEP=""
ONLY_STEP=""
SKIP_GEMINI=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)      DRY_RUN=1; shift ;;
    --from)         FROM_STEP="$2"; shift 2 ;;
    --only)         ONLY_STEP="$2"; shift 2 ;;
    --skip-gemini)  SKIP_GEMINI=1; shift ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# //'
      exit 0 ;;
    *) err "Unknown flag: $1"; exit 1 ;;
  esac
done

# ── preflight ─────────────────────────────────────────────────────────────────
step "Preflight checks"

# 1. venv
if [[ ! -f "$VENV/bin/python" ]]; then
  warn "No venv found at $VENV — creating one now…"
  python3 -m venv "$VENV"
fi
PYTHON="$VENV/bin/python"

# 2. dependencies
info "Installing / updating dependencies from requirements.txt…"
"$PYTHON" -m pip install -q -r "$SCRIPT_DIR/requirements.txt"

# 3. .env
if [[ ! -f "$REPO_ROOT/.env" ]]; then
  err ".env not found at $REPO_ROOT/.env"
  err "Copy .env.example → .env and fill in your keys."
  exit 1
fi

# 4. required env vars
set -a; source "$REPO_ROOT/.env"; set +a

MISSING=()
[[ -z "${SUPABASE_URL:-}"              ]] && MISSING+=("SUPABASE_URL")
[[ -z "${SUPABASE_ANON_KEY:-}"        ]] && MISSING+=("SUPABASE_ANON_KEY")
[[ -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]] && MISSING+=("SUPABASE_SERVICE_ROLE_KEY")

if [[ ${#MISSING[@]} -gt 0 ]]; then
  err "Missing required env vars: ${MISSING[*]}"
  err "Set them in $REPO_ROOT/.env"
  exit 1
fi

# Warn (don't fail) about optional keys
[[ -z "${GEMINI_API_KEY:-}"   ]] && warn "GEMINI_API_KEY not set — Gemini steps will fail"
[[ -z "${X_BEARER_TOKEN:-}"   ]] && warn "X_BEARER_TOKEN not set — tweet scraper will fail (use --dry-run)"

info "Preflight OK"

# ── step runner ───────────────────────────────────────────────────────────────
STEPS_RAN=0
STEPS_SKIPPED=0
STEPS_FAILED=0
SKIP_UNTIL_FOUND=0
[[ -n "$FROM_STEP" ]] && SKIP_UNTIL_FOUND=1

run_step() {
  local name="$1"; shift   # script name (no .py)
  local label="$1"; shift  # display label
  local cmd=("$@")         # remaining args = command

  # --only: skip everything except the target
  if [[ -n "$ONLY_STEP" && "$name" != "$ONLY_STEP" ]]; then
    return
  fi

  # --from: skip steps until we hit the named one
  if [[ $SKIP_UNTIL_FOUND -eq 1 ]]; then
    if [[ "$name" == "$FROM_STEP" ]]; then
      SKIP_UNTIL_FOUND=0
    else
      info "  skipping $label (before --from $FROM_STEP)"
      STEPS_SKIPPED=$((STEPS_SKIPPED + 1))
      return
    fi
  fi

  step "$label"
  START=$(date +%s)
  if "${cmd[@]}"; then
    END=$(date +%s)
    info "  ✓ done in $((END - START))s"
    STEPS_RAN=$((STEPS_RAN + 1))
  else
    END=$(date +%s)
    err "  ✗ FAILED after $((END - START))s"
    STEPS_FAILED=$((STEPS_FAILED + 1))
    # Don't exit — continue remaining steps so you see the full picture
  fi
}

# ── pipeline steps ────────────────────────────────────────────────────────────

# Step 1: scrape X
if [[ $DRY_RUN -eq 1 ]]; then
  # --from-file loads a saved JSON instead of hitting the X API
  CACHE="$SCRIPT_DIR/last_fetch.json"
  if [[ ! -f "$CACHE" ]]; then
    warn "  --dry-run: no last_fetch.json found at $CACHE — skipping tweet scrape"
    STEPS_SKIPPED=$((STEPS_SKIPPED + 1))
  else
    run_step "scrape_tweets" "1/7 Scrape X (dry-run from $CACHE)" \
      "$PYTHON" "$SCRIPT_DIR/scrape_tweets.py" --from-file "$CACHE"
  fi
else
  run_step "scrape_tweets" "1/7 Scrape X (@CMOTamilnadu via API v2)" \
    "$PYTHON" "$SCRIPT_DIR/scrape_tweets.py"
fi

# Step 2: scrape Reddit
run_step "scrape_reddit" "2/7 Scrape Reddit (JSON fallback)" \
  "$PYTHON" "$SCRIPT_DIR/scrape_reddit.py"

# Step 3: scrape CM events
if [[ $SKIP_GEMINI -eq 0 ]]; then
  run_step "scrape_cm_events" "3/7 Scrape CM events (RSS + Chennai District + TN NIC)" \
    "$PYTHON" "$SCRIPT_DIR/scrape_cm_events.py"
else
  info "  skipping scrape_cm_events (--skip-gemini)"
  STEPS_SKIPPED=$((STEPS_SKIPPED + 1))
fi

# Step 4: scrape grievances (CM Helpline + GCC PGR)
run_step "scrape_grievances" "4/7 Scrape CM Helpline + GCC grievance stats" \
  "$PYTHON" "$SCRIPT_DIR/scrape_grievances.py"

# Step 5: categorize signals
if [[ $SKIP_GEMINI -eq 0 ]]; then
  run_step "categorize_signals" "5/7 Categorize signals (rules → Gemini)" \
    "$PYTHON" "$SCRIPT_DIR/categorize_signals.py"
else
  info "  skipping categorize_signals (--skip-gemini)"
  STEPS_SKIPPED=$((STEPS_SKIPPED + 1))
fi

# Step 6: cluster into issues
if [[ $SKIP_GEMINI -eq 0 ]]; then
  run_step "cluster_issues" "6/7 Cluster signals into Issues (Gemini)" \
    "$PYTHON" "$SCRIPT_DIR/cluster_issues.py"
else
  info "  skipping cluster_issues (--skip-gemini)"
  STEPS_SKIPPED=$((STEPS_SKIPPED + 1))
fi

# Step 7: link CM events ↔ issues
if [[ $SKIP_GEMINI -eq 0 ]]; then
  run_step "link_events_to_issues" "7/7 Link CM events ↔ Issues (Gemini)" \
    "$PYTHON" "$SCRIPT_DIR/link_events_to_issues.py"
else
  info "  skipping link_events_to_issues (--skip-gemini)"
  STEPS_SKIPPED=$((STEPS_SKIPPED + 1))
fi

# ── summary ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━ Pipeline complete ━━━${RESET}"
echo -e "  ${GREEN}✓ ran:     $STEPS_RAN${RESET}"
[[ $STEPS_SKIPPED -gt 0 ]] && echo -e "  ${YELLOW}⊘ skipped: $STEPS_SKIPPED${RESET}"
[[ $STEPS_FAILED  -gt 0 ]] && echo -e "  ${RED}✗ failed:  $STEPS_FAILED${RESET}" && exit 1
echo ""
