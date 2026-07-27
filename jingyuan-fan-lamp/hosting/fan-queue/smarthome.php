<?php

declare(strict_types=1);

require __DIR__ . '/lib.php';
require __DIR__ . '/alexa_verify.php';
require __DIR__ . '/smarthome_devices.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    fan_queue_json(405, ['error' => 'method not allowed']);
}

$rawBody = file_get_contents('php://input');
if ($rawBody === false || $rawBody === '') {
    fan_queue_json(400, ['error' => 'empty body']);
}

$config = fan_queue_config();
$proxyToken = (string) ($config['LAMBDA_PROXY_TOKEN'] ?? '');
$fromLambdaProxy = smarthome_lambda_proxy_token_valid($proxyToken);

if (!$fromLambdaProxy) {
    alexa_verify_request($rawBody);
}

$payload = json_decode($rawBody, true);
if (!is_array($payload)) {
    fan_queue_json(400, ['error' => 'invalid json']);
}

$directive = $payload['directive'] ?? null;
if (!is_array($directive)) {
    fan_queue_json(400, ['error' => 'missing directive']);
}

$header = $directive['header'] ?? [];
$namespace = (string) ($header['namespace'] ?? '');
$name = (string) ($header['name'] ?? '');
$messageId = (string) ($header['messageId'] ?? smarthome_uuid());
$correlationToken = isset($header['correlationToken']) ? (string) $header['correlationToken'] : null;
$endpointId = (string) ($directive['endpoint']['endpointId'] ?? '');

smarthome_log('directive ' . $namespace . '.' . $name . ' endpoint=' . $endpointId);

$key = $namespace . '|' . $name;

if ($key === 'Alexa.Discovery|Discover') {
    smarthome_handle_discover($correlationToken);
}

if ($key === 'Alexa.PowerController|TurnOn') {
    smarthome_handle_power($endpointId, true, $correlationToken);
}

if ($key === 'Alexa.PowerController|TurnOff') {
    smarthome_handle_power($endpointId, false, $correlationToken);
}

if ($key === 'Alexa|ReportState') {
    smarthome_handle_report_state($endpointId, $correlationToken);
}

if ($namespace === 'Alexa.Authorization' && $name === 'AcceptGrant') {
    smarthome_handle_accept_grant($correlationToken);
}

smarthome_send_error(
    $endpointId,
    $correlationToken,
    'INVALID_DIRECTIVE',
    'Unsupported directive: ' . $namespace . '.' . $name
);

function smarthome_uuid(): string
{
    $bytes = random_bytes(16);
    $bytes[6] = chr((ord($bytes[6]) & 0x0f) | 0x40);
    $bytes[8] = chr((ord($bytes[8]) & 0x3f) | 0x80);
    $hex = bin2hex($bytes);

    return sprintf(
        '%s-%s-%s-%s-%s',
        substr($hex, 0, 8),
        substr($hex, 8, 4),
        substr($hex, 12, 4),
        substr($hex, 16, 4),
        substr($hex, 20, 12)
    );
}

function smarthome_log(string $message): void
{
    $line = gmdate('c') . ' ' . $message . PHP_EOL;
    @file_put_contents(fan_queue_data_dir() . '/smarthome.log', $line, FILE_APPEND);
}

function smarthome_lambda_proxy_token_valid(string $proxyToken): bool
{
    if ($proxyToken === '') {
        return false;
    }

    $headerToken = alexa_get_request_header('X-Lambda-Proxy-Token');
    if ($headerToken !== '' && hash_equals($proxyToken, $headerToken)) {
        return true;
    }

    $auth = alexa_get_request_header('Authorization');
    if ($auth !== '' && preg_match('/^Bearer\s+(\S+)/i', $auth, $matches)) {
        return hash_equals($proxyToken, $matches[1]);
    }

    return false;
}

function smarthome_now_iso(): string
{
    return gmdate('Y-m-d\TH:i:s\Z');
}

function smarthome_send_json(array $payload): void
{
    http_response_code(200);
    header('Content-Type: application/json');
    echo json_encode($payload, JSON_UNESCAPED_SLASHES);
    exit;
}

function smarthome_event_header(string $namespace, string $name, ?string $correlationToken): array
{
    $header = [
        'namespace' => $namespace,
        'name' => $name,
        'payloadVersion' => '3',
        'messageId' => smarthome_uuid(),
    ];
    if ($correlationToken !== null && $correlationToken !== '') {
        $header['correlationToken'] = $correlationToken;
    }
    return $header;
}

function smarthome_power_property(string $powerState): array
{
    return [
        'namespace' => 'Alexa.PowerController',
        'name' => 'powerState',
        'value' => $powerState,
        'timeOfSample' => smarthome_now_iso(),
        'uncertaintyInMilliseconds' => 500,
    ];
}

function smarthome_handle_discover(?string $correlationToken): void
{
    $endpoints = [];
    foreach (smarthome_devices() as $endpointId => $device) {
        $endpoints[] = smarthome_build_endpoint($endpointId, $device);
    }

    smarthome_send_json([
        'event' => [
            'header' => smarthome_event_header('Alexa.Discovery', 'Discover.Response', $correlationToken),
            'payload' => [
                'endpoints' => $endpoints,
            ],
        ],
    ]);
}

function smarthome_handle_power(string $endpointId, bool $turnOn, ?string $correlationToken): void
{
    $device = smarthome_device($endpointId);
    if ($device === null) {
        smarthome_send_error($endpointId, $correlationToken, 'NO_SUCH_ENDPOINT', 'Unknown endpoint');
    }

    $command = $turnOn ? $device['commandOn'] : $device['commandOff'];
    $result = fan_queue_enqueue($command, false, 'alexa-smarthome');
    smarthome_log('enqueued ' . $command . ' id=' . $result['id']);

    smarthome_save_power_state($endpointId, $turnOn ? 'ON' : 'OFF');

    $event = [
        'header' => smarthome_event_header('Alexa', 'Response', $correlationToken),
        'endpoint' => [
            'endpointId' => $endpointId,
        ],
        'payload' => new stdClass(),
    ];

    smarthome_send_json([
        'event' => $event,
        'context' => [
            'properties' => [
                smarthome_power_property($turnOn ? 'ON' : 'OFF'),
            ],
        ],
    ]);
}

function smarthome_handle_report_state(string $endpointId, ?string $correlationToken): void
{
    $device = smarthome_device($endpointId);
    if ($device === null) {
        smarthome_send_error($endpointId, $correlationToken, 'NO_SUCH_ENDPOINT', 'Unknown endpoint');
    }

    $powerState = smarthome_load_power_state($endpointId);

    smarthome_send_json([
        'event' => [
            'header' => smarthome_event_header('Alexa', 'StateReport', $correlationToken),
            'endpoint' => [
                'endpointId' => $endpointId,
            ],
            'payload' => new stdClass(),
        ],
        'context' => [
            'properties' => [
                smarthome_power_property($powerState),
            ],
        ],
    ]);
}

function smarthome_handle_accept_grant(?string $correlationToken): void
{
    smarthome_send_json([
        'event' => [
            'header' => smarthome_event_header('Alexa.Authorization', 'AcceptGrant.Response', $correlationToken),
            'payload' => new stdClass(),
        ],
    ]);
}

function smarthome_send_error(
    string $endpointId,
    ?string $correlationToken,
    string $type,
    string $message
): void {
    smarthome_log('error ' . $type . ': ' . $message);

    $payload = [
        'event' => [
            'header' => smarthome_event_header('Alexa', 'ErrorResponse', $correlationToken),
            'payload' => [
                'type' => $type,
                'message' => $message,
            ],
        ],
    ];

    if ($endpointId !== '') {
        $payload['event']['endpoint'] = ['endpointId' => $endpointId];
    }

    smarthome_send_json($payload);
}

function smarthome_state_path(): string
{
    return fan_queue_data_dir() . '/smarthome_state.json';
}

function smarthome_load_power_state(string $endpointId): string
{
    $path = smarthome_state_path();
    if (!is_readable($path)) {
        return 'OFF';
    }
    $raw = file_get_contents($path);
    if ($raw === false) {
        return 'OFF';
    }
    $data = json_decode($raw, true);
    if (!is_array($data)) {
        return 'OFF';
    }
    $state = $data[$endpointId] ?? 'OFF';
    return $state === 'ON' ? 'ON' : 'OFF';
}

function smarthome_save_power_state(string $endpointId, string $powerState): void
{
    $path = smarthome_state_path();
    $data = [];
    if (is_readable($path)) {
        $raw = file_get_contents($path);
        if ($raw !== false) {
            $decoded = json_decode($raw, true);
            if (is_array($decoded)) {
                $data = $decoded;
            }
        }
    }
    $data[$endpointId] = $powerState === 'ON' ? 'ON' : 'OFF';
    file_put_contents($path, json_encode($data, JSON_UNESCAPED_SLASHES));
    chmod($path, 0600);
}
