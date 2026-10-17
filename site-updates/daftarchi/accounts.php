<?php
header('Content-Type: application/json; charset=utf-8');

$key = 'daftarchi-webakery-mail';
$file = __DIR__ . '/accounts.json';
$plans = ['3m', '6m', '12m', '50y', '7d'];
$statuses = ['paid', 'pending', 'canceled'];
$methods = ['cash', 'card', 'gateway'];

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'GET') {
    echo json_encode(['ok' => true, 'service' => 'daftarchi-accounts'], JSON_UNESCAPED_UNICODE);
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'service' => 'daftarchi-accounts', 'error' => 'method'], JSON_UNESCAPED_UNICODE);
    exit;
}

$data = json_decode(file_get_contents('php://input'), true);
if (!is_array($data) || !hash_equals($key, (string) ($data['key'] ?? ''))) {
    http_response_code(403);
    echo json_encode(['ok' => false, 'service' => 'daftarchi-accounts', 'error' => 'key'], JSON_UNESCAPED_UNICODE);
    exit;
}

if ((string) ($data['action'] ?? '') !== 'save' || !is_array($data['items'] ?? null)) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'service' => 'daftarchi-accounts', 'error' => 'action'], JSON_UNESCAPED_UNICODE);
    exit;
}

function account_item(array $item, array $plans, array $statuses, array $methods): ?array
{
    $phone = preg_replace('/\D/', '', (string) ($item['phone'] ?? ''));
    $shop = preg_replace('/\D/', '', (string) ($item['shop_phone'] ?? ''));
    $name = trim((string) ($item['buyer_name'] ?? ''));
    $plan = (string) ($item['plan'] ?? '');
    $status = (string) ($item['status'] ?? '');
    $local = (int) ($item['local_id'] ?? 0);
    $payable = (int) ($item['payable'] ?? 0);
    $method = (string) ($item['payment_method'] ?? '');
    if (strlen($phone) < 10 || strlen($phone) > 15 || $name === '' || mb_strlen($name) > 80) {
        return null;
    }
    if (!in_array($plan, $plans, true) || !in_array($status, $statuses, true) || $local < 1) {
        return null;
    }
    if ($payable < 0 || $payable > 5000000000) {
        return null;
    }
    return [
        'shop_phone' => substr($shop, 0, 15),
        'local_id' => $local,
        'buyer_name' => mb_substr($name, 0, 80),
        'phone' => $phone,
        'plan' => $plan,
        'title' => mb_substr(trim((string) ($item['title'] ?? '')), 0, 40),
        'payable' => $payable,
        'status' => $status,
        'starts_at' => substr((string) ($item['starts_at'] ?? ''), 0, 40),
        'ends_at' => substr((string) ($item['ends_at'] ?? ''), 0, 40),
        'gateway_ref' => substr(preg_replace('/[^0-9A-Za-z_-]/', '', (string) ($item['gateway_ref'] ?? '')), 0, 64),
        'payment_method' => in_array($method, $methods, true) ? $method : '',
        'updated_at' => gmdate('c'),
    ];
}

$handle = fopen($file, 'c+');
if ($handle === false) {
    http_response_code(500);
    echo json_encode(['ok' => false, 'service' => 'daftarchi-accounts', 'error' => 'storage'], JSON_UNESCAPED_UNICODE);
    exit;
}
flock($handle, LOCK_EX);
$raw = stream_get_contents($handle);
$store = json_decode($raw ?: '[]', true);
if (!is_array($store)) {
    $store = [];
}
$map = [];
foreach ($store as $row) {
    if (is_array($row)) {
        $map[($row['shop_phone'] ?? '') . '|' . ($row['local_id'] ?? '')] = $row;
    }
}
$ids = [];
foreach (array_slice($data['items'], 0, 40) as $item) {
    if (!is_array($item)) {
        continue;
    }
    $clean = account_item($item, $plans, $statuses, $methods);
    if ($clean === null) {
        continue;
    }
    $map[$clean['shop_phone'] . '|' . $clean['local_id']] = $clean;
    $ids[] = $clean['local_id'];
}
$rows = array_values($map);
if (count($rows) > 2000) {
    $rows = array_slice($rows, -2000);
}
rewind($handle);
ftruncate($handle, 0);
fwrite($handle, json_encode($rows, JSON_UNESCAPED_UNICODE));
fflush($handle);
flock($handle, LOCK_UN);
fclose($handle);

echo json_encode([
    'ok' => true,
    'service' => 'daftarchi-accounts',
    'saved' => count($ids),
    'ids' => $ids,
], JSON_UNESCAPED_UNICODE);
