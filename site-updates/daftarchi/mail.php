<?php
header('Content-Type: application/json; charset=utf-8');

$key = 'daftarchi-webakery-mail';

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'GET') {
    echo json_encode(['ok' => true, 'service' => 'daftarchi-mail'], JSON_UNESCAPED_UNICODE);
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

$to = strtolower(trim((string) ($data['to'] ?? '')));
$subject = trim((string) ($data['subject'] ?? ''));
$text = (string) ($data['text'] ?? '');
if (!preg_match('/^[a-z0-9._%+\-]+@(gmail|googlemail)\.com$/', $to) || $subject === '' || $text === '') {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'fields'], JSON_UNESCAPED_UNICODE);
    exit;
}

$headers = [
    'Content-Type: text/plain; charset=UTF-8',
    'From: Daftarchi <noreply@webakery.ir>',
    'Reply-To: noreply@webakery.ir',
];
$sent = false;
$wp = dirname(__DIR__) . '/wp-load.php';
if (is_file($wp)) {
    require_once $wp;
    $sent = (bool) wp_mail($to, $subject, $text, $headers);
}
if (!$sent) {
    $encoded = '=?UTF-8?B?' . base64_encode($subject) . '?=';
    $sent = @mail(
        $to,
        $encoded,
        $text,
        implode("\r\n", array_merge(['MIME-Version: 1.0'], $headers)),
        '-fnoreply@webakery.ir'
    );
}

if (!$sent) {
    http_response_code(502);
    echo json_encode(['ok' => false, 'error' => 'mail'], JSON_UNESCAPED_UNICODE);
    exit;
}

echo json_encode(['ok' => true, 'service' => 'daftarchi-mail'], JSON_UNESCAPED_UNICODE);
