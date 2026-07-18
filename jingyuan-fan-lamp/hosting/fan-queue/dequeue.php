<?php

declare(strict_types=1);

require __DIR__ . '/lib.php';

if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    fan_queue_json(405, ['error' => 'method not allowed']);
}

fan_queue_require_dequeue_auth();
$job = fan_queue_dequeue();
if ($job === null) {
    http_response_code(204);
    exit;
}

fan_queue_json(200, $job);
