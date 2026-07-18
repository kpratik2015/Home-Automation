<?php

declare(strict_types=1);

require __DIR__ . '/lib.php';
require __DIR__ . '/alexa_verify.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    fan_queue_json(405, ['error' => 'method not allowed']);
}

$rawBody = file_get_contents('php://input');
if ($rawBody === false || $rawBody === '') {
    fan_queue_json(400, ['error' => 'empty body']);
}

alexa_verify_request($rawBody);
$payload = json_decode($rawBody, true);
if (!is_array($payload)) {
    fan_queue_json(400, ['error' => 'invalid json']);
}

$request = $payload['request'] ?? [];
$type = $request['type'] ?? '';
$intentName = $request['intent']['name'] ?? '';

if ($type === 'LaunchRequest') {
    alexa_respond(null, true);
}

if ($type === 'SessionEndedRequest') {
    http_response_code(200);
    header('Content-Type: application/json');
    echo json_encode(['version' => '1.0'], JSON_UNESCAPED_SLASHES);
    exit;
}

if ($type !== 'IntentRequest') {
    alexa_respond(null, true);
}

$commandMap = [
    'TurnOnFan' => 'fan-on',
    'TurnOffFan' => 'fan-off',
    'TurnOnLight' => 'light-on',
    'TurnOffLight' => 'light-off',
];

if ($intentName === 'AMAZON.HelpIntent') {
    alexa_respond('Say turn on the fan or turn off the fan.', true);
}

if (in_array($intentName, ['AMAZON.CancelIntent', 'AMAZON.StopIntent'], true)) {
    alexa_respond(null, true);
}

$command = $commandMap[$intentName] ?? null;
if ($command === null) {
    alexa_log_skill_error('unknown intent: ' . $intentName);
    alexa_respond(null, true);
}

$result = fan_queue_enqueue($command, false, 'alexa-skill');
alexa_log_skill_error('enqueued ' . $command . ' id=' . $result['id']);

alexa_respond(null, true);

function alexa_respond(?string $text, bool $endSession): void
{
    http_response_code(200);
    header('Content-Type: application/json');

    $response = [
        'version' => '1.0',
        'response' => [
            'shouldEndSession' => $endSession,
        ],
    ];

    if ($text !== null && $text !== '') {
        $response['response']['outputSpeech'] = [
            'type' => 'PlainText',
            'text' => $text,
        ];
    }

    echo json_encode($response, JSON_UNESCAPED_SLASHES);
    exit;
}
