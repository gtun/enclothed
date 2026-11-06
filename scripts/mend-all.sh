#!/usr/bin/env bash
# Fill in the blank fields on every garment in a wardrobe. Run on the server, after deploying.
# Usage: scripts/mend-all.sh [user id]   (default: 1, the owner)
#
# It backs up the database, mends 5 garments, and asks before doing the rest. Each garment is one
# paid AI call. It only fills blanks, and it's safe to run again: garments it has already tried
# are skipped, so an interrupted run picks up where it left off.
set -euo pipefail
cd ~/enclothed

USER_ID="${1:-1}"
ENCLOTHED=(docker exec enclothed /app/.venv/bin/enclothed)

mkdir -p ~/db-backups
BACKUP="pre-mend-$(date +%F-%H%M).db"
docker exec enclothed /app/.venv/bin/python -c \
  "import sqlite3; sqlite3.connect('/app/data/enclothed.db').backup(sqlite3.connect('/app/data/$BACKUP'))"
mv "data/$BACKUP" ~/db-backups/
echo "Backed up the database to ~/db-backups/$BACKUP"

echo
echo "Trying 5 garments first..."
"${ENCLOTHED[@]}" mend --user-id "$USER_ID" --limit 5 || true

echo
read -r -p "Check those on enclothe.me, including the cost on the Usage page. Mend the rest? [y/N] " answer
if [[ "$answer" != [yY]* ]]; then
  echo "Stopped. Run this script again whenever you're ready."
  exit 0
fi

"${ENCLOTHED[@]}" mend --user-id "$USER_ID"

echo
echo "If this was your wardrobe, refresh the demo so it gets the new details:"
echo "  docker exec enclothed /app/.venv/bin/enclothed demo-seed"
