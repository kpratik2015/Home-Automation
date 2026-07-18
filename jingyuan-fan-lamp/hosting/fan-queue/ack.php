<?php

declare(strict_types=1);

require __DIR__ . '/lib.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    fan_queue_json(405, ['error' => 'method not allowed']);
}

fan_queue_require_dequeue_auth();
$body = fan_queue_read_json_body();
$id = $body['id'] ?? null;
$status = $body['status'] ?? '';

if (!is_int($id) && !(is_string($id) && ctype_digit($id))) {
    fan_queue_json(400, ['error' => 'missing id']);
}

if (!is_string($status) || $status === '') {
    fan_queue_json(400, ['error' => 'missing status']);
}

fan_queue_ack((int) $id, $status);
