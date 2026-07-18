<?php

declare(strict_types=1);

const ALLOWED_COMMANDS = ['fan-on', 'fan-off', 'light-on', 'light-off'];

function fan_queue_config(): array
{
    static $config = null;
    if ($config !== null) {
        return $config;
    }

    $local = __DIR__ . '/config.local.php';
    if (!is_readable($local)) {
        http_response_code(500);
        header('Content-Type: application/json');
        echo json_encode(['error' => 'missing config.local.php']);
        exit;
    }

    $config = require $local;
    return $config;
}

function fan_queue_data_dir(): string
{
    $dir = __DIR__ . '/data';
    if (!is_dir($dir)) {
        mkdir($dir, 0700, true);
    }
    return $dir;
}

function fan_queue_pdo(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }

    $dbPath = fan_queue_data_dir() . '/queue.sqlite';
    $pdo = new PDO('sqlite:' . $dbPath, null, null, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);
    $pdo->exec('PRAGMA busy_timeout = 5000');
    $pdo->exec('PRAGMA journal_mode = WAL');
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            leased_at TEXT NULL
        )'
    );
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS enqueue_rate (
            token_hash TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )'
    );
    $pdo->exec(
        'CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at)'
    );

    return $pdo;
}

function fan_queue_json(int $status, array $payload): void
{
    http_response_code($status);
    header('Content-Type: application/json');
    echo json_encode($payload, JSON_UNESCAPED_SLASHES);
    exit;
}

function fan_queue_read_json_body(): array
{
    $raw = file_get_contents('php://input');
    if ($raw === false || $raw === '') {
        fan_queue_json(400, ['error' => 'empty body']);
    }
    $data = json_decode($raw, true);
    if (!is_array($data)) {
        fan_queue_json(400, ['error' => 'invalid json']);
    }
    return $data;
}

function fan_queue_bearer_token(): string
{
    $header = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
    if (preg_match('/^Bearer\s+(.+)$/i', $header, $matches) !== 1) {
        fan_queue_json(401, ['error' => 'missing bearer token']);
    }
    return trim($matches[1]);
}

function fan_queue_require_enqueue_auth(): void
{
    $config = fan_queue_config();
    $token = fan_queue_bearer_token();
    if (!hash_equals((string) $config['ENQUEUE_TOKEN'], $token)) {
        fan_queue_json(401, ['error' => 'unauthorized']);
    }
}

function fan_queue_require_dequeue_auth(): void
{
    $config = fan_queue_config();
    $token = fan_queue_bearer_token();
    if (!hash_equals((string) $config['DEQUEUE_TOKEN'], $token)) {
        fan_queue_json(401, ['error' => 'unauthorized']);
    }
}

function fan_queue_validate_command(string $command): void
{
    if (!in_array($command, ALLOWED_COMMANDS, true)) {
        fan_queue_json(400, ['error' => 'invalid command']);
    }
}

function fan_queue_check_rate_limit(string $token): void
{
    $config = fan_queue_config();
    $limit = (int) ($config['ENQUEUE_RATE_LIMIT'] ?? 5);
    $window = (int) ($config['ENQUEUE_RATE_WINDOW'] ?? 60);
    $hash = hash('sha256', $token);
    $pdo = fan_queue_pdo();
    $cutoff = time() - $window;

    $pdo->prepare('DELETE FROM enqueue_rate WHERE created_at < :cutoff')
        ->execute(['cutoff' => $cutoff]);

    $stmt = $pdo->prepare(
        'SELECT COUNT(*) AS count FROM enqueue_rate WHERE token_hash = :hash AND created_at >= :cutoff'
    );
    $stmt->execute(['hash' => $hash, 'cutoff' => $cutoff]);
    $count = (int) $stmt->fetchColumn();
    if ($count >= $limit) {
        fan_queue_json(429, ['error' => 'rate limit exceeded']);
    }

    $pdo->prepare(
        'INSERT INTO enqueue_rate (token_hash, created_at) VALUES (:hash, :created_at)'
    )->execute(['hash' => $hash, 'created_at' => time()]);
}

function fan_queue_active_count(PDO $pdo): int
{
    $stmt = $pdo->query(
        "SELECT COUNT(*) FROM jobs WHERE status IN ('pending', 'leased')"
    );
    return (int) $stmt->fetchColumn();
}

function fan_queue_requeue_expired_leases(PDO $pdo): void
{
    $config = fan_queue_config();
    $leaseSeconds = (int) ($config['LEASE_SECONDS'] ?? 30);
    $cutoff = gmdate('Y-m-d\TH:i:s\Z', time() - $leaseSeconds);

    $pdo->prepare(
        "UPDATE jobs
         SET status = 'pending', leased_at = NULL
         WHERE status = 'leased' AND leased_at IS NOT NULL AND leased_at < :cutoff"
    )->execute(['cutoff' => $cutoff]);
}

function fan_queue_enqueue(string $command, bool $applyRateLimit, string $rateToken): array
{
    fan_queue_validate_command($command);
    $pdo = fan_queue_pdo();

    if ($applyRateLimit) {
        fan_queue_check_rate_limit($rateToken);
    }

    $config = fan_queue_config();
    $maxPending = (int) ($config['MAX_PENDING'] ?? 50);

    $pdo->beginTransaction();
    try {
        fan_queue_requeue_expired_leases($pdo);

        $stmt = $pdo->prepare(
            "SELECT id FROM jobs WHERE command = :command AND status = 'pending' ORDER BY id ASC LIMIT 1"
        );
        $stmt->execute(['command' => $command]);
        $existing = $stmt->fetch();
        if ($existing !== false) {
            $pdo->commit();
            return ['ok' => true, 'id' => (int) $existing['id'], 'coalesced' => true];
        }

        if (fan_queue_active_count($pdo) >= $maxPending) {
            $pdo->rollBack();
            fan_queue_json(429, ['error' => 'queue full']);
        }

        $now = gmdate('Y-m-d\TH:i:s\Z');
        $insert = $pdo->prepare(
            "INSERT INTO jobs (command, status, created_at, leased_at) VALUES (:command, 'pending', :created_at, NULL)"
        );
        $insert->execute(['command' => $command, 'created_at' => $now]);
        $id = (int) $pdo->lastInsertId();
        $pdo->commit();
        return ['ok' => true, 'id' => $id, 'coalesced' => false];
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        throw $e;
    }
}

function fan_queue_dequeue(): ?array
{
    $pdo = fan_queue_pdo();
    $pdo->beginTransaction();
    try {
        fan_queue_requeue_expired_leases($pdo);

        $stmt = $pdo->query(
            "SELECT id, command FROM jobs WHERE status = 'pending' ORDER BY created_at ASC, id ASC LIMIT 1"
        );
        $row = $stmt->fetch();
        if ($row === false) {
            $pdo->commit();
            return null;
        }

        $now = gmdate('Y-m-d\TH:i:s\Z');
        $update = $pdo->prepare(
            "UPDATE jobs SET status = 'leased', leased_at = :leased_at WHERE id = :id AND status = 'pending'"
        );
        $update->execute(['leased_at' => $now, 'id' => $row['id']]);
        if ($update->rowCount() !== 1) {
            $pdo->rollBack();
            return fan_queue_dequeue();
        }

        $pdo->commit();
        return ['id' => (int) $row['id'], 'command' => $row['command']];
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) {
            $pdo->rollBack();
        }
        throw $e;
    }
}

function fan_queue_ack(int $id, string $status): void
{
    if (!in_array($status, ['done', 'failed'], true)) {
        fan_queue_json(400, ['error' => 'invalid status']);
    }

    $pdo = fan_queue_pdo();
    $stmt = $pdo->prepare(
        "UPDATE jobs SET status = :status WHERE id = :id AND status = 'leased'"
    );
    $stmt->execute(['status' => $status, 'id' => $id]);
    if ($stmt->rowCount() !== 1) {
        fan_queue_json(404, ['error' => 'job not found or not leased']);
    }
    fan_queue_json(200, ['ok' => true, 'id' => $id, 'status' => $status]);
}
