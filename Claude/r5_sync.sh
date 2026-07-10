#!/usr/bin/env bash
#
# r5_sync.sh — push raw DRF data + analysis results to the shared Google Drive
# folder so collaborators always see the latest files.
#
# SAFE BY DESIGN:
#   • Additive only — no --delete, so it never removes anything at the destination.
#   • Never touches the live SQLite DB or its lock files (excluded).
#   • Writes to the local CloudStorage mount; Drive uploads in the background.
#
# Usage:
#   Claude/r5_sync.sh            # do the sync, print a per-step summary
#   Claude/r5_sync.sh --dry-run  # show what WOULD transfer, change nothing
#
set -uo pipefail

SRC="$HOME/Documents/HorseRacing"
DEST="$HOME/Library/CloudStorage/GoogleDrive-hadalian@gmail.com/My Drive/Horse racing/Shared Data"

DRY=""
if [[ "${1:-}" == "--dry-run" || "${1:-}" == "-n" ]]; then
  DRY="-n"
  echo "🧪 DRY RUN — nothing will be copied"
fi

if [[ ! -d "$DEST" ]]; then
  echo "❌ Destination not found: $DEST"
  echo "   Is Google Drive for Desktop running and the Shared Data folder present?"
  exit 1
fi

run_step () {  # $1 = label, rest = rsync args
  local label="$1"; shift
  local out n
  # -i (itemize) lists one line per file; '>f' = a file being sent (new or changed).
  # This count is accurate in BOTH real and --dry-run modes (unlike --stats).
  out=$(rsync -a $DRY -i "$@" 2>&1)
  local rc=$?
  if [[ $rc -ne 0 ]]; then
    echo "  ⚠️  $label: rsync error (rc=$rc)"
    echo "$out" | tail -3 | sed 's/^/       /'
    return 1
  fi
  n=$(echo "$out" | grep -cE '^>f')
  if [[ "$n" == "0" ]]; then
    echo "  ✅ $label: no changes"
  else
    echo "  📤 $label: $n file(s) transferred/updated"
  fi
}

echo "🔄 Syncing to shared Drive: $DEST"

# 1) Raw DRF entry files
run_step "DRF (files 2/)" --exclude='.DS_Store' \
  "$SRC/files 2/" "$DEST/files 2/"

# 2) Results (chart PDFs, aggregate xlsx, .md reports) — DB + locks excluded
run_step "Results/" --exclude='.DS_Store' --exclude='*.db' --exclude='*.db-wal' \
  --exclude='*.db-shm' --exclude='*.textClipping' --exclude='2025/' \
  "$SRC/Results/" "$DEST/Results/"

# 3) Per-card analysis .txt files (they save to repo root, not Results/) →
#    delivered into Results/ so collaborators get them alongside the xlsx.
run_step "Analysis .txt" --exclude='.DS_Store' --include='*_R5_analysis.txt' \
  --exclude='*' "$SRC/" "$DEST/Results/"

echo "✔ Sync complete."
