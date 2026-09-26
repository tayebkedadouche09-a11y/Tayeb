#!/usr/bin/env sh
set -eu
DB_PATH="${TAYEB_DB_PATH:-./app/tayeb.db}"
BACKUP_DIR="${TAYEB_BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
STORAGE_PATH="${TAYEB_STORAGE_PATH:-./app/storage}"
python - "$DB_PATH" "$BACKUP_DIR/tayeb-$STAMP.db" <<'PY'
import sqlite3,sys,os
src,dst=sys.argv[1:3]
if not os.path.exists(src):
    raise SystemExit("Database not found: "+src)
s=sqlite3.connect(src)
d=sqlite3.connect(dst)
with d:
    s.backup(d)
d.close();s.close()
print(dst)
PY
if [ -d "$STORAGE_PATH" ]; then
  tar -czf "$BACKUP_DIR/tayeb-storage-$STAMP.tar.gz" -C "$STORAGE_PATH" .
  echo "$BACKUP_DIR/tayeb-storage-$STAMP.tar.gz"
fi
