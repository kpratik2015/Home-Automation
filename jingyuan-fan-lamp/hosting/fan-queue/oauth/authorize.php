<?php

declare(strict_types=1);

require __DIR__ . '/../oauth_lib.php';

if (oauth_client_id() === '' || oauth_client_secret() === '') {
    http_response_code(500);
    echo 'OAuth is not configured on the server.';
    exit;
}

$clientId = (string) ($_GET['client_id'] ?? '');
$redirectUri = (string) ($_GET['redirect_uri'] ?? '');
$state = (string) ($_GET['state'] ?? '');
$responseType = (string) ($_GET['response_type'] ?? '');
$confirm = (string) ($_GET['confirm'] ?? '') === '1';

if ($clientId === '' || $redirectUri === '' || $state === '' || $responseType !== 'code') {
    http_response_code(400);
    echo 'Invalid authorization request.';
    exit;
}

if (!hash_equals(oauth_client_id(), $clientId)) {
    http_response_code(400);
    echo 'Unknown client.';
    exit;
}

if (!oauth_validate_redirect_uri($redirectUri)) {
    http_response_code(400);
    echo 'Invalid redirect URI.';
    exit;
}

if ($confirm) {
    $code = oauth_create_auth_code($redirectUri);
    $separator = str_contains($redirectUri, '?') ? '&' : '?';
    $location = $redirectUri . $separator . http_build_query([
        'code' => $code,
        'state' => $state,
    ]);
    header('Location: ' . $location, true, 302);
    exit;
}

$query = http_build_query([
    'client_id' => $clientId,
    'redirect_uri' => $redirectUri,
    'state' => $state,
    'response_type' => $responseType,
    'scope' => (string) ($_GET['scope'] ?? ''),
    'confirm' => '1',
]);

header('Content-Type: text/html; charset=utf-8');
?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Link Center Fan Light</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 28rem; margin: 4rem auto; padding: 0 1rem; }
    h1 { font-size: 1.25rem; }
    p { color: #444; line-height: 1.5; }
    a.button {
      display: inline-block; margin-top: 1rem; padding: 0.75rem 1rem;
      background: #232f3e; color: #fff; text-decoration: none; border-radius: 0.5rem;
    }
  </style>
</head>
<body>
  <h1>Link Center Fan Light</h1>
  <p>Allow Alexa to control Center Fan and Center Light in your home.</p>
  <a class="button" href="authorize.php?<?php echo htmlspecialchars($query, ENT_QUOTES); ?>">Link account</a>
</body>
</html>
