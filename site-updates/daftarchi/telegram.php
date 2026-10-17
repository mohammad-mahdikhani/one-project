<?php
header('Content-Type: application/json; charset=utf-8');

$key = 'daftarchi-webakery-mail';

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'GET') {
    echo json_encode(['ok' => true, 'service' => 'daftarchi-telegram'], JSON_UNESCAPED_UNICODE);
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'error' => 'method'], JSON_UNESCAPED_UNICODE);
    exit;
}

$raw = file_get_contents('php://input');
$data = json_decode($raw, true);
if (!is_array($data) || !hash_equals($key, (string) ($data['key'] ?? ''))) {
    http_response_code(403);
    echo json_encode(['ok' => false, 'error' => 'key'], JSON_UNESCAPED_UNICODE);
    exit;
}

$text = trim((string) ($data['text'] ?? ''));
if ($text === '') {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'text'], JSON_UNESCAPED_UNICODE);
    exit;
}

$configPath = __DIR__ . '/telegram.json';
$config = is_file($configPath) ? json_decode((string) file_get_contents($configPath), true) : null;
$token = is_array($config) ? trim((string) ($config['bot_token'] ?? '')) : '';
$chat = is_array($config) ? trim((string) ($config['chat_id'] ?? '')) : '';
if (!preg_match('/^\d{6,15}:[A-Za-z0-9_-]{20,}$/', $token) || !preg_match('/^-?\d{1,20}$/', $chat)) {
    http_response_code(503);
    echo json_encode(['ok' => false, 'error' => 'token'], JSON_UNESCAPED_UNICODE);
    exit;
}

$payload = json_encode(['chat_id' => $chat, 'text' => mb_substr($text, 0, 3500)], JSON_UNESCAPED_UNICODE);
$context = stream_context_create([
    'http' => [
        'method' => 'POST',
        'header' => "Content-Type: application/json\r\n",
        'content' => $payload,
        'timeout' => 8,
        'ignore_errors' => true,
    ],
]);
$response = @file_get_contents('https://api.telegram.org/bot' . $token . '/sendMessage', false, $context);
$decoded = json_decode((string) $response, true);
if (!is_array($decoded) || empty($decoded['ok'])) {
    http_response_code(502);
    echo json_encode(['ok' => false, 'error' => 'telegram'], JSON_UNESCAPED_UNICODE);
    exit;
}

echo json_encode(['ok' => true], JSON_UNESCAPED_UNICODE);
