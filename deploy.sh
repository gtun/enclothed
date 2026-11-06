#!/usr/bin/env bash
# Deploy the latest main. Run on the server.
set -euo pipefail
cd ~/enclothed

git pull --ff-only
docker tag enclothed enclothed:previous    # keep the current version, for rollback
docker build -t enclothed .                # the old version stays up during this

docker stop enclothed
docker rm enclothed

mkdir -p ~/db-backups
cp data/enclothed.db ~/db-backups/enclothed-$(date +%F-%H%M).db

docker run -d --name enclothed --restart unless-stopped \
  -p 127.0.0.1:8000:8000 --env-file .env -v "$PWD/data:/app/data" enclothed

# The app takes a few seconds to start, and a connection fails until it has.
for _ in {1..30}; do
  if curl -fsS -o /dev/null http://127.0.0.1:8000/ 2>/dev/null; then
    echo "Deployed."
    exit 0
  fi
  sleep 1
done
echo "App isn't responding. Run: docker logs enclothed"
exit 1
