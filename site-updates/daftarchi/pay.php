<?php
header('Content-Type: application/json; charset=utf-8');

$key = 'daftarchi-webakery-mail';
$merchant = '6a331116da557b902563c32f';

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'GET') {
    echo json_encode(['ok' => true, 'service' => 'daftarchi-pay'], JSON_UNESCAPED_UNICODE);
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'error' => 'method'], JSON_UNESCAPED_UNICODE);
    exit;
}

$data = json_decode(file_get_contents('php://input'), true);
if (!is_array($data) || !hash_equals($key, (string) ($data['key'] ?? ''))) {
    http_response_code(403);
    echo json_encode(['ok' => false, 'error' => 'key'], JSON_UNESCAPED_UNICODE);
    exit;
}

function zibal_call(string $url, array $payload): array
{
    $json = json_encode($payload, JSON_UNESCAPED_UNICODE);
    if (function_exists('curl_init')) {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_POST => true,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'Accept: application/json'],
            CURLOPT_POSTFIELDS => $json,
            CURLOPT_TIMEOUT => 20,
        ]);
        $raw = curl_exec($ch);
        curl_close($ch);
    } else {
        $context = stream_context_create([
            'http' => [
                'method' => 'POST',
                'header' => "Content-Type: application/json\r\nAccept: application/json\r\n",
                'content' => $json,
                'timeout' => 20,
                'ignore_errors' => true,
            ],
        ]);
        $raw = @file_get_contents($url, false, $context);
    }
    $body = json_decode((string) $raw, true);
    return is_array($body) ? $body : [];
}

$action = (string) ($data['action'] ?? '');
if ($action === 'request') {
    $amount = (int) ($data['amount'] ?? 0);
    if ($amount < 10000 || $amount > 5000000000) {
        http_response_code(400);
        echo json_encode(['ok' => false, 'error' => 'amount'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    $callback = trim((string) ($data['callbackUrl'] ?? 'https://webakery.ir'));
    if (!preg_match('#^https://#', $callback)) {
        $callback = 'https://webakery.ir';
    }
    $body = zibal_call('https://gateway.zibal.ir/v1/request', [
        'merchant' => $merchant,
        'amount' => $amount,
        'callbackUrl' => $callback,
        'description' => mb_substr(trim((string) ($data['description'] ?? 'لایسنس دفترچی')), 0, 250),
        'orderId' => substr(preg_replace('/[^0-9A-Za-z_-]/', '', (string) ($data['orderId'] ?? '')), 0, 40),
        'mobile' => preg_replace('/\D/', '', (string) ($data['mobile'] ?? '')),
    ]);
    $track = $body['trackId'] ?? '';
    if (($body['result'] ?? 0) != 100 || $track === '') {
        http_response_code(502);
        echo json_encode([
            'ok' => false,
            'service' => 'daftarchi-pay',
            'error' => (string) ($body['message'] ?? 'zibal'),
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }
    echo json_encode([
        'ok' => true,
        'service' => 'daftarchi-pay',
        'result' => 100,
        'trackId' => $track,
        'payUrl' => 'https://gateway.zibal.ir/start/' . $track,
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

if ($action === 'verify') {
    $track = $data['trackId'] ?? '';
    if ($track === '' || $track === null) {
        http_response_code(400);
        echo json_encode(['ok' => false, 'error' => 'track'], JSON_UNESCAPED_UNICODE);
        exit;
    }
    $body = zibal_call('https://gateway.zibal.ir/v1/verify', [
        'merchant' => $merchant,
        'trackId' => is_numeric($track) ? (int) $track : $track,
    ]);
    $result = $body['result'] ?? 0;
    if (!in_array($result, [100, 201, '100', '201'], true)) {
        http_response_code(409);
        echo json_encode([
            'ok' => false,
            'service' => 'daftarchi-pay',
            'result' => $result,
            'error' => (string) ($body['message'] ?? 'unpaid'),
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }
    echo json_encode([
        'ok' => true,
        'service' => 'daftarchi-pay',
        'result' => $result,
        'refNumber' => (string) ($body['refNumber'] ?? $track),
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

http_response_code(400);
echo json_encode(['ok' => false, 'error' => 'action'], JSON_UNESCAPED_UNICODE);
