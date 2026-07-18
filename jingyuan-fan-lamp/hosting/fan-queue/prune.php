<?php

declare(strict_types=1);

require __DIR__ . '/lib.php';

$days = 7;
if (PHP_SAPI === 'cli' && isset($argv[1]) && ctype_digit($argv[1])) {
    $days = (int) $argv[1];
}

$cutoff = gmdate('Y-m-d\TH:i:s\Z', time() - ($days * 86400));
$pdo = fan_queue_pdo();
$stmt = $pdo->prepare(
    "DELETE FROM jobs WHERE status IN ('done', 'failed') AND created_at < :cutoff"
);
$stmt->execute(['cutoff' => $cutoff]);
$deleted = $stmt->rowCount();

if (PHP_SAPI === 'cli') {
    fwrite(STDOUT, "Pruned {$deleted} jobs older than {$days} days\n");
    exit(0);
}

fan_queue_json(200, ['ok' => true, 'deleted' => $deleted]);
