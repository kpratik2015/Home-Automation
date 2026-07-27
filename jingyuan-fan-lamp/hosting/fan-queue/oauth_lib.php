<?php

declare(strict_types=1);

require __DIR__ . '/lib.php';
require __DIR__ . '/alexa_verify.php';

function oauth_client_id(): string
{
    return (string) (fan_queue_config()['OAUTH_CLIENT_ID'] ?? '');
}

function oauth_client_secret(): string
{
    return (string) (fan_queue_config()['OAUTH_CLIENT_SECRET'] ?? '');
}

function oauth_access_token(): string
{
    return (string) (fan_queue_config()['OAUTH_ACCESS_TOKEN'] ?? '');
}

function oauth_refresh_token(): string
{
    return (string) (fan_queue_config()['OAUTH_REFRESH_TOKEN'] ?? '');
}

function oauth_codes_path(): string
{
    return fan_queue_data_dir() . '/oauth_codes.json';
}

function oauth_validate_redirect_uri(string $uri): bool
{
    if ($uri === '' || !str_starts_with($uri, 'https://')) {
        return false;
    }

    $parts = parse_url($uri);
    if ($parts === false) {
        return false;
    }

    $host = strtolower((string) ($parts['host'] ?? ''));
    return str_ends_with($host, '.amazon.com')
        || str_ends_with($host, '.amazon.in')
        || $host === 'amazon.com'
        || $host === 'amazon.in';
}

function oauth_client_matches(string $clientId, string $clientSecret): bool
{
    $expectedId = oauth_client_id();
    $expectedSecret = oauth_client_secret();
    if ($expectedId === '' || $expectedSecret === '') {
        return false;
    }

    return hash_equals($expectedId, $clientId) && hash_equals($expectedSecret, $clientSecret);
}

function oauth_read_credentials(): array
{
    $clientId = (string) ($_POST['client_id'] ?? '');
    $clientSecret = (string) ($_POST['client_secret'] ?? '');

    if ($clientId !== '' && $clientSecret !== '') {
        return ['client_id' => $clientId, 'client_secret' => $clientSecret];
    }

    $auth = alexa_get_request_header('Authorization');
    if ($auth !== '' && preg_match('/^Basic\s+(\S+)/i', $auth, $matches)) {
        $decoded = base64_decode($matches[1], true);
        if ($decoded !== false && str_contains($decoded, ':')) {
            [$id, $secret] = explode(':', $decoded, 2);
            return ['client_id' => $id, 'client_secret' => $secret];
        }
    }

    return ['client_id' => $clientId, 'client_secret' => $clientSecret];
}

function oauth_read_token_body(): array
{
    if ($_POST !== []) {
        return $_POST;
    }

    $raw = file_get_contents('php://input');
    if ($raw === false || $raw === '') {
        return [];
    }

    $json = json_decode($raw, true);
    if (is_array($json)) {
        return $json;
    }

    parse_str($raw, $parsed);
    return is_array($parsed) ? $parsed : [];
}

function oauth_load_codes(): array
{
    $path = oauth_codes_path();
    if (!is_readable($path)) {
        return [];
    }

    $raw = file_get_contents($path);
    if ($raw === false) {
        return [];
    }

    $data = json_decode($raw, true);
    return is_array($data) ? $data : [];
}

function oauth_save_codes(array $codes): void
{
    $now = time();
    $filtered = [];
    foreach ($codes as $code => $entry) {
        if (!is_array($entry)) {
            continue;
        }
        $expires = (int) ($entry['expires'] ?? 0);
        if ($expires > $now) {
            $filtered[$code] = $entry;
        }
    }

    $path = oauth_codes_path();
    file_put_contents($path, json_encode($filtered, JSON_UNESCAPED_SLASHES));
    chmod($path, 0600);
}

function oauth_create_auth_code(string $redirectUri): string
{
    $code = bin2hex(random_bytes(24));
    $codes = oauth_load_codes();
    $codes[$code] = [
        'redirect_uri' => $redirectUri,
        'expires' => time() + 600,
        'used' => false,
    ];
    oauth_save_codes($codes);

    return $code;
}

function oauth_consume_auth_code(string $code, string $redirectUri): bool
{
    $codes = oauth_load_codes();
    if (!isset($codes[$code]) || !is_array($codes[$code])) {
        return false;
    }

    $entry = $codes[$code];
    if (($entry['used'] ?? true) === true) {
        return false;
    }
    if ((int) ($entry['expires'] ?? 0) < time()) {
        return false;
    }
    if (!hash_equals((string) ($entry['redirect_uri'] ?? ''), $redirectUri)) {
        return false;
    }

    $codes[$code]['used'] = true;
    oauth_save_codes($codes);

    return true;
}

function oauth_token_response(): array
{
    return [
        'access_token' => oauth_access_token(),
        'token_type' => 'bearer',
        'expires_in' => 3600,
        'refresh_token' => oauth_refresh_token(),
    ];
}

function oauth_json_error(string $error, int $status = 400): void
{
    fan_queue_json($status, ['error' => $error]);
}
