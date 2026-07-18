<?php

declare(strict_types=1);

require __DIR__ . '/lib.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    fan_queue_json(405, ['error' => 'method not allowed']);
}

fan_queue_require_enqueue_auth();
$body = fan_queue_read_json_body();
$command = $body['command'] ?? '';
if (!is_string($command) || $command === '') {
    fan_queue_json(400, ['error' => 'missing command']);
}

$config = fan_queue_config();
$result = fan_queue_enqueue($command, true, (string) $config['ENQUEUE_TOKEN']);
fan_queue_json(200, $result);
