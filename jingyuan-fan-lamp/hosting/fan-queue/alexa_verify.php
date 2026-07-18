<?php

declare(strict_types=1);

function alexa_get_request_header(string $name): string
{
    $serverKey = 'HTTP_' . strtoupper(str_replace('-', '_', $name));
    if (!empty($_SERVER[$serverKey])) {
        return (string) $_SERVER[$serverKey];
    }

    if (function_exists('getallheaders')) {
        $headers = getallheaders();
        if (is_array($headers)) {
            foreach ($headers as $key => $value) {
                if (strcasecmp((string) $key, $name) === 0) {
                    return (string) $value;
                }
            }
        }
    }

    return '';
}

function alexa_log_skill_error(string $message): void
{
    $line = gmdate('c') . ' ' . $message . PHP_EOL;
    @file_put_contents(fan_queue_data_dir() . '/skill.log', $line, FILE_APPEND);
}

function alexa_verify_request(string $rawBody): void
{
    $signatureCertChainUrl = alexa_get_request_header('SignatureCertChainUrl');
    $signature = alexa_get_request_header('Signature');

    if ($signatureCertChainUrl === '' || $signature === '') {
        alexa_log_skill_error('missing signature headers');
        fan_queue_json(400, ['error' => 'missing alexa signature headers']);
    }

    if (!alexa_validate_cert_url($signatureCertChainUrl)) {
        alexa_log_skill_error('invalid cert url: ' . $signatureCertChainUrl);
        fan_queue_json(400, ['error' => 'invalid signature cert url']);
    }

    $pem = alexa_fetch_cert_chain($signatureCertChainUrl);
    if ($pem === null) {
        alexa_log_skill_error('could not fetch cert chain');
        fan_queue_json(400, ['error' => 'could not fetch cert chain']);
    }

    if (!alexa_verify_cert_chain($pem)) {
        alexa_log_skill_error('invalid cert chain');
        fan_queue_json(400, ['error' => 'invalid cert chain']);
    }

    if (!alexa_verify_signature($rawBody, $signature, $pem)) {
        alexa_log_skill_error('invalid signature');
        fan_queue_json(400, ['error' => 'invalid signature']);
    }

    $payload = json_decode($rawBody, true);
    if (!is_array($payload)) {
        fan_queue_json(400, ['error' => 'invalid alexa json']);
    }

    alexa_verify_timestamp($payload);
}

function alexa_validate_cert_url(string $url): bool
{
    $parts = parse_url($url);
    if ($parts === false) {
        return false;
    }
    if (($parts['scheme'] ?? '') !== 'https') {
        return false;
    }

    $host = strtolower($parts['host'] ?? '');
    $allowedHosts = ['s3.amazonaws.com'];
    if (!in_array($host, $allowedHosts, true) && !preg_match('/^s3[.-][a-z0-9-]+\.amazonaws\.com$/', $host)) {
        return false;
    }

    $path = $parts['path'] ?? '';
    return str_starts_with($path, '/echo.api/');
}

function alexa_cert_cache_path(string $url): string
{
    $dir = fan_queue_data_dir() . '/certs';
    if (!is_dir($dir)) {
        mkdir($dir, 0700, true);
    }
    return $dir . '/' . hash('sha256', $url) . '.pem';
}

function alexa_fetch_cert_chain(string $url): ?string
{
    $cachePath = alexa_cert_cache_path($url);
    if (is_readable($cachePath) && (time() - filemtime($cachePath)) < 3600) {
        $cached = file_get_contents($cachePath);
        return $cached === false ? null : $cached;
    }

    $context = stream_context_create([
        'http' => [
            'timeout' => 10,
            'follow_location' => 0,
        ],
        'ssl' => [
            'verify_peer' => true,
            'verify_peer_name' => true,
        ],
    ]);

    $pem = @file_get_contents($url, false, $context);
    if ($pem === false || $pem === '') {
        return null;
    }

    file_put_contents($cachePath, $pem);
    chmod($cachePath, 0600);
    return $pem;
}

function alexa_verify_cert_chain(string $pem): bool
{
    if (!preg_match_all(
        '/-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----/s',
        $pem,
        $matches
    )) {
        return false;
    }

    $certs = [];
    foreach ($matches[0] as $certPem) {
        $cert = openssl_x509_read($certPem);
        if ($cert === false) {
            return false;
        }
        $certs[] = $cert;
    }

    if ($certs === []) {
        return false;
    }

    $leaf = $certs[0];
    $parsed = openssl_x509_parse($leaf);
    if ($parsed === false) {
        return false;
    }

    $validFrom = $parsed['validFrom_time_t'] ?? 0;
    $validTo = $parsed['validTo_time_t'] ?? 0;
    $now = time();
    if ($now < $validFrom || $now > $validTo) {
        return false;
    }

    $san = $parsed['extensions']['subjectAltName'] ?? '';
    if (strpos($san, 'DNS:echo-api.amazon.com') === false) {
        return false;
    }

    return true;
}

function alexa_verify_signature(string $rawBody, string $signatureBase64, string $pem): bool
{
    if (!preg_match(
        '/-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----/s',
        $pem,
        $match
    )) {
        return false;
    }

    $cert = openssl_x509_read($match[0]);
    if ($cert === false) {
        return false;
    }

    $publicKey = openssl_pkey_get_public($cert);
    if ($publicKey === false) {
        return false;
    }

    $signature = base64_decode($signatureBase64, true);
    if ($signature === false) {
        return false;
    }

    return openssl_verify($rawBody, $signature, $publicKey, OPENSSL_ALGO_SHA1) === 1;
}

function alexa_verify_timestamp(array $payload): void
{
    $timestamp = $payload['request']['timestamp'] ?? '';
    if ($timestamp === '') {
        fan_queue_json(400, ['error' => 'missing request timestamp']);
    }

    $requestTime = strtotime($timestamp);
    if ($requestTime === false) {
        fan_queue_json(400, ['error' => 'invalid request timestamp']);
    }

    if (abs(time() - $requestTime) > 150) {
        fan_queue_json(400, ['error' => 'request timestamp too old']);
    }
}
