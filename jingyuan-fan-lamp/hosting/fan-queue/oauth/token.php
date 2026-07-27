<?php

declare(strict_types=1);

require __DIR__ . '/../oauth_lib.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    oauth_json_error('method not allowed', 405);
}

if (oauth_client_id() === '' || oauth_client_secret() === '') {
    oauth_json_error('oauth not configured', 500);
}

$body = oauth_read_token_body();
$credentials = oauth_read_credentials();
$clientId = $credentials['client_id'];
$clientSecret = $credentials['client_secret'];

if (!oauth_client_matches($clientId, $clientSecret)) {
    oauth_json_error('invalid_client', 401);
}

$grantType = (string) ($body['grant_type'] ?? '');

if ($grantType === 'authorization_code') {
    $code = (string) ($body['code'] ?? '');
    $redirectUri = (string) ($body['redirect_uri'] ?? '');
    if ($code === '' || $redirectUri === '') {
        oauth_json_error('invalid_request');
    }
    if (!oauth_consume_auth_code($code, $redirectUri)) {
        oauth_json_error('invalid_grant', 400);
    }
    fan_queue_json(200, oauth_token_response());
}

if ($grantType === 'refresh_token') {
    $refreshToken = (string) ($body['refresh_token'] ?? '');
    if ($refreshToken === '' || !hash_equals(oauth_refresh_token(), $refreshToken)) {
        oauth_json_error('invalid_grant', 400);
    }
    fan_queue_json(200, oauth_token_response());
}

oauth_json_error('unsupported_grant_type');
