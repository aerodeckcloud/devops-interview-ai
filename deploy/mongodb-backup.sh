#!/usr/bin/env bash
# Encrypted mongodump plus the avatar upload volume.
# Run on the droplet from the repo root. Requires BACKUP_PASSPHRASE.
# Mongo credentials are read from the repo-root .env. Values already exported win.
# Optional Spaces upload: SPACES_BUCKET, SPACES_ENDPOINT, SPACES_ACCESS_KEY, SPACES_SECRET_KEY.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

load_env_file() {
  local file="$1" line key val
  [ -f "$file" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in
      ''|\#*) continue ;;
    esac
    case "$line" in
      export\ *) line="${line#export }" ;;
    esac
    case "$line" in
      *=*) ;;
      *) continue ;;
    esac
    key="${line%%=*}"
    val="${line#*=}"
    case "$val" in
      \"*\") val="${val#\"}"; val="${val%\"}" ;;
      \'*\') val="${val#\'}"; val="${val%\'}" ;;
    esac
    if [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && [ -z "${!key+x}" ]; then
      export "$key=$val"
    fi
  done < "$file"
}

load_env_file "$ROOT/.env"

: "${BACKUP_PASSPHRASE:?Set BACKUP_PASSPHRASE}"
: "${MONGO_ROOT_USERNAME:?Set MONGO_ROOT_USERNAME}"
: "${MONGO_ROOT_PASSWORD:?Set MONGO_ROOT_PASSWORD}"
DB_NAME="${MONGODB_DB_NAME:-ops_mentor_ai}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BACKUP_DIR:-$ROOT/backups}"
mkdir -p "$OUT"

# Honor COMPOSE_FILE when the droplet uses the production override.
COMPOSE=(docker compose)

ARCHIVE="$OUT/mongo-${STAMP}.archive.gz"
ENCRYPTED="$ARCHIVE.enc"
UPLOADS="$OUT/uploads-${STAMP}.tar.gz"
UPLOADS_ENC="$UPLOADS.enc"

"${COMPOSE[@]}" exec -T mongodb \
  mongodump \
  --username "$MONGO_ROOT_USERNAME" \
  --password "$MONGO_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --db "$DB_NAME" \
  --archive --gzip > "$ARCHIVE"

openssl enc -aes-256-cbc -pbkdf2 -salt \
  -pass env:BACKUP_PASSPHRASE \
  -in "$ARCHIVE" -out "$ENCRYPTED"
rm -f "$ARCHIVE"

"${COMPOSE[@]}" exec -T backend \
  tar czf - -C /app/uploads . > "$UPLOADS"
openssl enc -aes-256-cbc -pbkdf2 -salt \
  -pass env:BACKUP_PASSPHRASE \
  -in "$UPLOADS" -out "$UPLOADS_ENC"
rm -f "$UPLOADS"

find "$OUT" -type f -name '*.enc' -mtime "+$KEEP_DAYS" -delete

if [ -n "${SPACES_BUCKET:-}" ]; then
  : "${SPACES_ENDPOINT:?Set SPACES_ENDPOINT}"
  : "${SPACES_ACCESS_KEY:?Set SPACES_ACCESS_KEY}"
  : "${SPACES_SECRET_KEY:?Set SPACES_SECRET_KEY}"
  AWS_ACCESS_KEY_ID="$SPACES_ACCESS_KEY" \
  AWS_SECRET_ACCESS_KEY="$SPACES_SECRET_KEY" \
  aws s3 cp "$ENCRYPTED" "s3://${SPACES_BUCKET}/mongo/$(basename "$ENCRYPTED")" \
    --endpoint-url "$SPACES_ENDPOINT"
  AWS_ACCESS_KEY_ID="$SPACES_ACCESS_KEY" \
  AWS_SECRET_ACCESS_KEY="$SPACES_SECRET_KEY" \
  aws s3 cp "$UPLOADS_ENC" "s3://${SPACES_BUCKET}/uploads/$(basename "$UPLOADS_ENC")" \
    --endpoint-url "$SPACES_ENDPOINT"
  cutoff="$(date -u -d "-${KEEP_DAYS} days" +%Y-%m-%d 2>/dev/null || date -u -v-"${KEEP_DAYS}"d +%Y-%m-%d)"
  prune_spaces_prefix() {
    local prefix="$1" old
    AWS_ACCESS_KEY_ID="$SPACES_ACCESS_KEY" \
    AWS_SECRET_ACCESS_KEY="$SPACES_SECRET_KEY" \
    aws s3 ls "s3://${SPACES_BUCKET}/${prefix}" --endpoint-url "$SPACES_ENDPOINT" \
      | awk -v cutoff="$cutoff" '$1 < cutoff {print $4}' \
      | while read -r old; do
          [ -n "$old" ] || continue
          AWS_ACCESS_KEY_ID="$SPACES_ACCESS_KEY" \
          AWS_SECRET_ACCESS_KEY="$SPACES_SECRET_KEY" \
          aws s3 rm "s3://${SPACES_BUCKET}/${prefix}${old}" --endpoint-url "$SPACES_ENDPOINT"
        done
  }
  prune_spaces_prefix "mongo/"
  prune_spaces_prefix "uploads/"
fi

echo "Wrote $ENCRYPTED and $UPLOADS_ENC"
