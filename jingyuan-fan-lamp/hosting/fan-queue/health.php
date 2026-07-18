<?php

declare(strict_types=1);

header('Content-Type: application/json');
echo json_encode(['ok' => true], JSON_UNESCAPED_SLASHES);
