# MongoDB auth and backups

Compose starts MongoDB with authentication. The port is not published. An old `mongodb_data` volume was created before this change and will not run `deploy/mongo-init.js`. Dump it first, remove that volume, then start again.

## Credentials

Put these in the repo-root `.env` (Compose reads that file for substitution). Use letters and numbers only so the URI does not need encoding.

```bash
MONGO_ROOT_USERNAME=opsroot
MONGO_ROOT_PASSWORD=replace-with-a-long-root-password
MONGO_APP_USERNAME=opsmentor
MONGO_APP_PASSWORD=replace-with-a-long-app-password
MONGODB_DB_NAME=ops_mentor_ai
```

The app user can read and write only `ops_mentor_ai`. The root user is for administration and backups. Do not commit either password.

Inside Compose the API uses:

```text
mongodb://<app-user>:<app-password>@mongodb:27017/ops_mentor_ai?authSource=ops_mentor_ai
```

A connection without a user is rejected once the volume has been initialized.

## Backup

On the droplet, from the repo root:

```bash
export BACKUP_PASSPHRASE='a long passphrase stored with the other secrets'
export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml
./deploy/mongodb-backup.sh
```

The script loads Mongo credentials from the repo-root `.env` and leaves variables that are already exported alone. It writes an encrypted `mongodump` archive and an encrypted copy of `/app/uploads`, keeps 14 days locally and in Spaces, and uploads both when these are set:

```bash
SPACES_BUCKET=ops-mentor-backups
SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
SPACES_ACCESS_KEY=...
SPACES_SECRET_KEY=...
```

Schedule it nightly with cron. `aws` CLI must be installed for the Spaces upload. Spaces speaks the S3 API.

## Restore check

Decrypt, then restore into a scratch database. Do this once before launch.

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_PASSPHRASE \
  -in backups/mongo-STAMP.archive.gz.enc -out /tmp/mongo.archive.gz

docker compose exec -T mongodb mongorestore \
  --username "$MONGO_ROOT_USERNAME" \
  --password "$MONGO_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --archive --gzip \
  --nsFrom 'ops_mentor_ai.*' \
  --nsTo 'restore_check.*' < /tmp/mongo.archive.gz

docker compose exec -T mongodb mongosh \
  --username "$MONGO_ROOT_USERNAME" \
  --password "$MONGO_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --eval 'db.getSiblingDB("restore_check").users.findOne()'
```

A known user document should print. Drop the scratch database after the check:

```bash
docker compose exec -T mongodb mongosh \
  --username "$MONGO_ROOT_USERNAME" \
  --password "$MONGO_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --eval 'db.getSiblingDB("restore_check").dropDatabase()'
rm -f /tmp/mongo.archive.gz
```

Token collections use a TTL index on `expires_at`, so expired refresh, verification, and reset tokens are removed by MongoDB.
