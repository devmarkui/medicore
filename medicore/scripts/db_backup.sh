#!/usr/bin/env bash
set -euo pipefail

# Configuration
PROJECT_DIR="/srv/medicore"
ENV_FILE="$PROJECT_DIR/.env"
BACKUP_DIR="/srv/backups/medicore"
RETENTION_DAYS=30
S3_BUCKET="${S3_BUCKET:-}" # optional, expects AWS CLI credentials

umask 077
mkdir -p "$BACKUP_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing environment file: $ENV_FILE" >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE"
REQUIRED_VARS=(MYSQL_DATABASE MYSQL_USER MYSQL_PASSWORD)
for var in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "Environment variable $var is not set" >&2
    exit 1
  fi
done

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
TMP_DIR="$(mktemp -d)"
SQL_FILE="${MYSQL_DATABASE}_${TIMESTAMP}.sql"
ARCHIVE_FILE="$BACKUP_DIR/${MYSQL_DATABASE}_${TIMESTAMP}.tar.gz"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "[ $(date) ] Starting MariaDB dump..."
docker compose --project-directory "$PROJECT_DIR" exec -T db \
  mariadb-dump -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" --single-transaction --routines --events "$MYSQL_DATABASE" \
  > "$TMP_DIR/$SQL_FILE"

echo "[ $(date) ] Compressing archive..."
tar -czf "$ARCHIVE_FILE" -C "$TMP_DIR" "$SQL_FILE"
sha256sum "$ARCHIVE_FILE" > "$ARCHIVE_FILE.sha256"

if [[ -n "$S3_BUCKET" ]]; then
  echo "[ $(date) ] Uploading backup to s3://$S3_BUCKET/"
  aws s3 cp "$ARCHIVE_FILE" "s3://$S3_BUCKET/"
  aws s3 cp "$ARCHIVE_FILE.sha256" "s3://$S3_BUCKET/"
fi

echo "[ $(date) ] Applying retention policy (${RETENTION_DAYS} days)..."
find "$BACKUP_DIR" -type f -name '*.tar.gz' -mtime +"$RETENTION_DAYS" -print -delete
find "$BACKUP_DIR" -type f -name '*.tar.gz.sha256' -mtime +"$RETENTION_DAYS" -print -delete

echo "[ $(date) ] Backup completed: $ARCHIVE_FILE"
