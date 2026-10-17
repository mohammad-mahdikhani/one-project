<?php
header('X-Content-Type-Options: nosniff');

$key = 'daftarchi-webakery-mail';
$root = __DIR__;
$manifest_path = $root . '/version.json';
$release_dir = $root . '/releases';
$app_limit = 80 * 1024 * 1024;
$plugin_limit = 30 * 1024 * 1024;

function release_h(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES, 'UTF-8');
}

function release_cut(string $value, int $width): string
{
    if (function_exists('mb_substr')) {
        return mb_substr($value, 0, $width);
    }
    if (preg_match('/^.{0,' . $width . '}/us', $value, $match)) {
        return $match[0];
    }
    return substr($value, 0, $width);
}

function release_json(int $status, array $body): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($body, JSON_UNESCAPED_UNICODE);
    exit;
}

function release_fail(string $error, int $status = 400): void
{
    if (release_wants_json()) {
        release_json($status, ['ok' => false, 'service' => 'daftarchi-releases', 'error' => $error]);
    }
    release_page($error, null);
}

function release_wants_json(): bool
{
    $accept = (string) ($_SERVER['HTTP_ACCEPT'] ?? '');
    return (($_GET['format'] ?? '') === 'json') || strpos($accept, 'application/json') !== false;
}

function release_lines($value, int $limit, int $width): array
{
    $rows = is_string($value) ? preg_split('/\R/u', $value) : (is_array($value) ? $value : []);
    $lines = [];
    foreach ($rows as $row) {
        $text = trim((string) $row);
        if ($text === '') {
            continue;
        }
        $lines[] = release_cut($text, $width);
        if (count($lines) === $limit) {
            break;
        }
    }
    return $lines;
}

function release_version(string $value): string
{
    $value = trim($value);
    if (!preg_match('/^\d{1,3}(\.\d{1,3}){1,3}$/', $value)) {
        release_fail('شماره نسخه مثل 1.2.0 باشد');
    }
    return $value;
}

function release_read_manifest(string $path): array
{
    $raw = is_file($path) ? file_get_contents($path) : '';
    $data = json_decode($raw ?: '', true);
    if (!is_array($data)) {
        $data = [];
    }
    $plugins = [];
    foreach (is_array($data['plugins'] ?? null) ? $data['plugins'] : [] as $item) {
        if (!is_array($item)) {
            continue;
        }
        $id = (string) ($item['id'] ?? '');
        $url = (string) ($item['url'] ?? '');
        if (!preg_match('/^[a-z0-9][a-z0-9-]{0,30}$/', $id) || strpos($url, 'https://') !== 0) {
            continue;
        }
        $plugins[] = [
            'id' => $id,
            'name' => release_cut(trim((string) ($item['name'] ?? '')), 60),
            'version' => release_cut(trim((string) ($item['version'] ?? '')), 20),
            'url' => $url,
            'notes' => release_cut(trim((string) ($item['notes'] ?? '')), 300),
            'features' => release_lines($item['features'] ?? [], 6, 120),
        ];
    }
    return [
        'version' => trim((string) ($data['version'] ?? '0.0.0')),
        'url' => trim((string) ($data['url'] ?? '')),
        'notes' => release_cut(trim((string) ($data['notes'] ?? '')), 500),
        'features' => release_lines($data['features'] ?? [], 8, 160),
        'plugins' => array_slice($plugins, 0, 12),
    ];
}

function release_write_manifest(string $path, array $manifest): void
{
    $dir = dirname($path);
    if (!is_dir($dir) && !mkdir($dir, 0755, true)) {
        release_fail('پوشه نسخه ساخته نشد', 500);
    }
    $tmp = $path . '.tmp';
    $json = json_encode($manifest, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT);
    if ($json === false || file_put_contents($tmp, $json . "\n", LOCK_EX) === false) {
        release_fail('version.json نوشته نشد', 500);
    }
    if (!rename($tmp, $path)) {
        @unlink($tmp);
        release_fail('version.json جایگزین نشد', 500);
    }
}

function release_public_base(): string
{
    $host = strtolower((string) ($_SERVER['HTTP_HOST'] ?? 'webakery.ir'));
    $host = preg_replace('/[^a-z0-9.:-]/', '', $host);
    $host = preg_replace('/:443$/', '', $host);
    $script = str_replace('\\', '/', (string) ($_SERVER['SCRIPT_NAME'] ?? '/daftarchi/releases.php'));
    $dir = rtrim(dirname($script), '/');
    if ($dir === '/' || $dir === '.') {
        $dir = '';
    }
    return 'https://' . $host . $dir;
}

function release_store_upload(array $file, string $dest, int $limit, array $exts): void
{
    $error = (int) ($file['error'] ?? UPLOAD_ERR_NO_FILE);
    if ($error === UPLOAD_ERR_INI_SIZE || $error === UPLOAD_ERR_FORM_SIZE) {
        release_fail('حجم فایل از سقف آپلود هاست بیشتر است');
    }
    if ($error !== UPLOAD_ERR_OK || !is_uploaded_file((string) ($file['tmp_name'] ?? ''))) {
        release_fail('فایل نسخه انتخاب نشده');
    }
    $size = (int) ($file['size'] ?? 0);
    if ($size < 1 || $size > $limit) {
        release_fail('حجم فایل مجاز نیست');
    }
    $ext = strtolower(pathinfo((string) ($file['name'] ?? ''), PATHINFO_EXTENSION));
    if (!in_array($ext, $exts, true)) {
        release_fail($exts === ['exe'] ? 'فایل اپ باید exe باشد' : 'فایل پلاگین باید zip باشد');
    }
    $folder = dirname($dest);
    if (!is_dir($folder) && !mkdir($folder, 0755, true)) {
        release_fail('پوشه releases ساخته نشد', 500);
    }
    if (!move_uploaded_file((string) $file['tmp_name'], $dest)) {
        release_fail('فایل روی هاست ذخیره نشد', 500);
    }
}

function release_page(string $error, ?array $done): void
{
    global $manifest_path;
    header('Content-Type: text/html; charset=utf-8');
    $manifest = release_read_manifest($manifest_path);
    $features = $manifest['features'] ? implode("\n", $manifest['features']) : '';
    $plugin_rows = '';
    foreach ($manifest['plugins'] as $plugin) {
        $plugin_rows .= '<li>' . release_h($plugin['name'] . ' ' . $plugin['version']) . '</li>';
    }
    if ($plugin_rows === '') {
        $plugin_rows = '<li>هنوز پلاگینی منتشر نشده.</li>';
    }
    $alert = $error !== '' ? '<p class="bad">' . release_h($error) . '</p>' : '';
    $success = '';
    if ($done) {
        $lines = '';
        foreach ($done['features'] as $line) {
            $lines .= '<li>' . release_h($line) . '</li>';
        }
        $success = '<p class="ok">' . release_h($done['message']) . '</p><p>مشتری با باز کردن دفترچی این را می‌بیند.</p><ul>' . $lines . '</ul><p class="ltr"><a href="' . release_h($done['url']) . '">' . release_h($done['url']) . '</a></p>';
    }
    echo '<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>انتشار نسخه دفترچی</title><style>
      body{margin:0;background:#f6f1e8;color:#1c1915;font:16px/1.7 Tahoma,sans-serif}
      main{width:min(720px,calc(100% - 28px));margin:24px auto}
      form,section{background:#fffdf8;border:1px solid #e7dccb;border-radius:16px;padding:16px;margin:0 0 14px}
      h1{font-size:22px;margin:0 0 8px}h2{font-size:17px;margin:0 0 8px}
      label{display:block;margin:10px 0 4px}input,textarea{width:100%;box-sizing:border-box;border:1px solid #e7dccb;border-radius:10px;padding:8px;font:inherit}
      button{margin-top:12px;background:#9a3412;color:#fff;border:0;border-radius:999px;padding:8px 16px;font:inherit}
      .ok{background:#ecfdf3;border-radius:10px;padding:8px 10px}.bad{background:#fff1f2;border-radius:10px;padding:8px 10px}
      .ltr{direction:ltr;text-align:left}.hint{color:#57534e}
    </style></head><body><main><h1>انتشار نسخه دفترچی</h1>' . $alert . $success . '
      <section><h2>نسخه فعلی روی هاست</h2><p>نسخه <strong class="ltr">' . release_h($manifest['version']) . '</strong></p><p class="hint">' . release_h($manifest['notes']) . '</p><p>ویژگی‌ها:</p><p class="hint">' . nl2br(release_h($features)) . '</p><p>پلاگین‌ها:</p><ul>' . $plugin_rows . '</ul>
      <p class="hint">دفترچی هنگام باز شدن <span class="ltr">version.json</span> همین پوشه را می‌خواند. اگر عدد نسخه بالاتر از برنامه مشتری باشد، نوار به‌روزرسانی و همین ویژگی‌ها نشان داده می‌شود. فروش و حساب‌ها پاک نمی‌شوند.</p></section>
      <form method="post" enctype="multipart/form-data"><h2>نسخه جدید اپ</h2><input type="hidden" name="action" value="app">
        <label>کلید هاست</label><input name="key" type="password" required autocomplete="current-password">
        <label>شماره نسخه</label><input class="ltr" name="version" required placeholder="1.2.0" inputmode="decimal">
        <label>یک جمله برای مشتری</label><textarea name="notes" rows="2" required></textarea>
        <label>ویژگی‌های تازه، هر کدام یک خط</label><textarea name="features" rows="5" required></textarea>
        <label>فایل Daftarchi.exe</label><input name="file" type="file" accept=".exe,application/octet-stream" required>
        <button type="submit">انتشار اپ</button></form>
      <form method="post" enctype="multipart/form-data"><h2>پلاگین</h2><input type="hidden" name="action" value="plugin">
        <label>کلید هاست</label><input name="key" type="password" required autocomplete="current-password">
        <label>شناسه انگلیسی</label><input class="ltr" name="plugin_id" required placeholder="sms-kavenegar">
        <label>نام پلاگین</label><input name="plugin_name" required>
        <label>شماره نسخه</label><input class="ltr" name="version" required placeholder="1.0.0" inputmode="decimal">
        <label>یک جمله برای مشتری</label><textarea name="notes" rows="2"></textarea>
        <label>ویژگی‌ها، هر کدام یک خط</label><textarea name="features" rows="4"></textarea>
        <label>فایل zip</label><input name="file" type="file" accept=".zip,application/zip" required>
        <button type="submit">انتشار پلاگین</button></form>
    </main></body></html>';
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'GET') {
    if (release_wants_json()) {
        release_json(200, ['ok' => true, 'service' => 'daftarchi-releases']);
    }
    release_page('', null);
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    release_fail('روش درخواست مجاز نیست', 405);
}

if ($_POST === [] && $_FILES === [] && (int) ($_SERVER['CONTENT_LENGTH'] ?? 0) > 0) {
    release_fail('حجم فایل از سقف آپلود هاست بیشتر است');
}

if (!hash_equals($key, (string) ($_POST['key'] ?? ''))) {
    release_fail('کلید هاست نادرست است', 403);
}

$action = (string) ($_POST['action'] ?? '');
$version = release_version((string) ($_POST['version'] ?? ''));
$notes = release_cut(trim((string) ($_POST['notes'] ?? '')), 500);
$features = release_lines((string) ($_POST['features'] ?? ''), $action === 'plugin' ? 6 : 8, $action === 'plugin' ? 120 : 160);
$manifest = release_read_manifest($manifest_path);
$base = release_public_base();

if ($action === 'app') {
    if ($notes === '' || $features === []) {
        release_fail('جمله و ویژگی‌های نسخه را بنویسید');
    }
    if (!version_compare($version, $manifest['version'] ?: '0.0.0', '>')) {
        release_fail('شماره نسخه باید از نسخه فعلی بالاتر باشد');
    }
    $name = 'Daftarchi-' . $version . '.exe';
    release_store_upload($_FILES['file'] ?? [], $release_dir . '/' . $name, $app_limit, ['exe']);
    $url = $base . '/releases/' . $name;
    $manifest['version'] = $version;
    $manifest['url'] = $url;
    $manifest['notes'] = $notes;
    $manifest['features'] = $features;
    $manifest['published'] = gmdate('c');
    release_write_manifest($manifest_path, $manifest);
    if (release_wants_json()) {
        release_json(200, ['ok' => true, 'service' => 'daftarchi-releases', 'version' => $version, 'url' => $url]);
    }
    release_page('', ['message' => 'نسخه ' . $version . ' منتشر شد.', 'url' => $url, 'features' => $features]);
}

if ($action === 'plugin') {
    $plugin_id = strtolower(trim((string) ($_POST['plugin_id'] ?? '')));
    $plugin_name = release_cut(trim((string) ($_POST['plugin_name'] ?? '')), 60);
    if (!preg_match('/^[a-z0-9][a-z0-9-]{0,30}$/', $plugin_id) || $plugin_name === '') {
        release_fail('شناسه و نام پلاگین را کامل بنویسید');
    }
    $current = '0.0.0';
    foreach ($manifest['plugins'] as $plugin) {
        if ($plugin['id'] === $plugin_id) {
            $current = $plugin['version'] ?: '0.0.0';
        }
    }
    if (!version_compare($version, $current, '>')) {
        release_fail('شماره نسخه پلاگین باید بالاتر باشد');
    }
    $name = $plugin_id . '-' . $version . '.zip';
    release_store_upload($_FILES['file'] ?? [], $release_dir . '/' . $name, $plugin_limit, ['zip']);
    $url = $base . '/releases/' . $name;
    $next = [
        'id' => $plugin_id,
        'name' => $plugin_name,
        'version' => $version,
        'url' => $url,
        'notes' => $notes,
        'features' => $features,
    ];
    $plugins = [];
    $replaced = false;
    foreach ($manifest['plugins'] as $plugin) {
        if ($plugin['id'] === $plugin_id) {
            $plugins[] = $next;
            $replaced = true;
        } else {
            $plugins[] = $plugin;
        }
    }
    if (!$replaced) {
        $plugins[] = $next;
    }
    $manifest['plugins'] = array_slice($plugins, 0, 12);
    $manifest['published'] = gmdate('c');
    release_write_manifest($manifest_path, $manifest);
    if (release_wants_json()) {
        release_json(200, ['ok' => true, 'service' => 'daftarchi-releases', 'version' => $version, 'url' => $url]);
    }
    release_page('', ['message' => 'پلاگین ' . $plugin_name . ' منتشر شد.', 'url' => $url, 'features' => $features ?: [$plugin_name]]);
}

release_fail('نوع انتشار مشخص نیست');
