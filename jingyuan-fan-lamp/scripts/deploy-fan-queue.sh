#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$REPO_ROOT/hosting/fan-queue"
REMOTE="pratikkataria:public_html/home-automation/fan-queue/"

echo "Deploying fan-queue to $REMOTE"
rsync -av \
  --exclude 'config.local.php' \
  --exclude 'data/' \
  "$SOURCE/" "$REMOTE"

ssh pratikkataria 'mkdir -p public_html/home-automation/fan-queue/data/certs && chmod 700 public_html/home-automation/fan-queue/data public_html/home-automation/fan-queue/data/certs'

REMOTE_CONFIG="public_html/home-automation/fan-queue/config.local.php"
if ! ssh pratikkataria "test -f $REMOTE_CONFIG"; then
  ENQUEUE_TOKEN="$(openssl rand -hex 24)"
  DEQUEUE_TOKEN="$(openssl rand -hex 24)"
  ssh pratikkataria "cp public_html/home-automation/fan-queue/config.example.php $REMOTE_CONFIG"
  ssh pratikkataria "php -r \"
\\\$path = getenv('HOME') . '/$REMOTE_CONFIG';
\\\$config = require \\\$path;
\\\$config['ENQUEUE_TOKEN'] = '$ENQUEUE_TOKEN';
\\\$config['DEQUEUE_TOKEN'] = '$DEQUEUE_TOKEN';
\\\$export = var_export(\\\$config, true);
file_put_contents(\\\$path, '<?php' . PHP_EOL . PHP_EOL . 'declare(strict_types=1);' . PHP_EOL . PHP_EOL . 'return ' . \\\$export . ';' . PHP_EOL);
chmod(\\\$path, 0600);
\""
  echo ""
  echo "Created $REMOTE_CONFIG with new tokens."
  echo "ENQUEUE_TOKEN=$ENQUEUE_TOKEN"
  echo "DEQUEUE_TOKEN=$DEQUEUE_TOKEN"
  echo ""
  echo "Add DEQUEUE_TOKEN to config.local.py as QUEUE_DEQUEUE_TOKEN"
else
  echo "config.local.php already exists on server (not overwritten)."
fi

echo ""
echo "Health check:"
curl -fsS "https://pratikkataria.com/home-automation/fan-queue/health.php"
echo ""
