#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CLIENT_ID="${OAUTH_CLIENT_ID:-center-fan-light}"
CLIENT_SECRET="$(openssl rand -hex 32)"
ACCESS_TOKEN="$(openssl rand -hex 32)"
REFRESH_TOKEN="$(openssl rand -hex 32)"

REMOTE_CONFIG="public_html/home-automation/fan-queue/config.local.php"

ssh pratikkataria "php -r \"
\\\$path = getenv('HOME') . '/$REMOTE_CONFIG';
\\\$config = require \\\$path;
\\\$config['OAUTH_CLIENT_ID'] = '$CLIENT_ID';
\\\$config['OAUTH_CLIENT_SECRET'] = '$CLIENT_SECRET';
\\\$config['OAUTH_ACCESS_TOKEN'] = '$ACCESS_TOKEN';
\\\$config['OAUTH_REFRESH_TOKEN'] = '$REFRESH_TOKEN';
\\\$export = var_export(\\\$config, true);
file_put_contents(\\\$path, '<?php' . PHP_EOL . PHP_EOL . 'declare(strict_types=1);' . PHP_EOL . PHP_EOL . 'return ' . \\\$export . ';' . PHP_EOL);
chmod(\\\$path, 0600);
echo 'oauth-config-ok' . PHP_EOL;
\""

echo ""
echo "OAuth credentials saved to server config.local.php"
echo ""
echo "Alexa Developer Console → Build → Account linking:"
echo "  Authorization URI: https://pratikkataria.com/home-automation/fan-queue/oauth/authorize.php"
echo "  Access Token URI:    https://pratikkataria.com/home-automation/fan-queue/oauth/token.php"
echo "  Client ID:           $CLIENT_ID"
echo "  Client Secret:       $CLIENT_SECRET"
echo "  Auth Scheme:         Credentials in request body (or HTTP Basic)"
echo "  Access Token Scheme: Bearer"
echo "  Scope:               (leave empty)"
echo "  Domain list:         pratikkataria.com"
echo ""
echo "Then disable + re-enable Center Fan Light in Alexa app and link account."
