<?php
// Recibe el lead del Arquitecto de Academia y lo reenvía al webhook entrante de GoHighLevel.
// La URL del webhook va en api/config.php ('ghl_webhook_url').
header('Content-Type: application/json; charset=utf-8');
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo json_encode(['ok' => false]); exit; }
$body = json_decode(file_get_contents('php://input'), true);
if (!is_array($body)) { $body = []; }
$email = trim((string)($body['email'] ?? ''));
if (!preg_match('/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/', $email)) { http_response_code(400); echo json_encode(['ok' => false, 'error' => 'email']); exit; }
$clean = [];
foreach ($body as $k => $v) { $clean[$k] = is_string($v) ? mb_substr($v, 0, 500) : $v; }
$clean['fecha'] = gmdate('c');
$config = file_exists(__DIR__ . '/config.php') ? (include __DIR__ . '/config.php') : [];
$url = is_array($config) ? ($config['ghl_webhook_url'] ?? '') : '';
$code = 0;
if ($url) {
  $ch = curl_init($url);
  curl_setopt_array($ch, [CURLOPT_POST => true, CURLOPT_HTTPHEADER => ['Content-Type: application/json'], CURLOPT_POSTFIELDS => json_encode($clean, JSON_UNESCAPED_UNICODE), CURLOPT_RETURNTRANSFER => true, CURLOPT_TIMEOUT => 10]);
  curl_exec($ch);
  $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
  curl_close($ch);
} else { error_log('Lead recibido (sin webhook de GHL): ' . $email); }
$sheetsOk = false;
$hoja = file_exists(__DIR__ . '/config-hoja.php') ? (include __DIR__ . '/config-hoja.php') : [];
$sheetsUrl = is_array($hoja) ? ($hoja['sheets_url'] ?? '') : '';
if ($sheetsUrl) {
  $row = $clean; $row['clave'] = $hoja['sheets_key'] ?? '';
  $ch = curl_init($sheetsUrl);
  curl_setopt_array($ch, [CURLOPT_POST => true, CURLOPT_HTTPHEADER => ['Content-Type: text/plain'], CURLOPT_POSTFIELDS => json_encode($row, JSON_UNESCAPED_UNICODE), CURLOPT_RETURNTRANSFER => true, CURLOPT_FOLLOWLOCATION => true, CURLOPT_TIMEOUT => 15]);
  $r = curl_exec($ch); curl_close($ch);
  $sheetsOk = trim((string)$r) === 'ok';
}
echo json_encode(['ok' => true, 'forwarded' => $code >= 200 && $code < 300, 'sheet' => $sheetsOk]);
