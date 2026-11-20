<?php
// Formulario de contacto de migracionconayuda.com
// Envía cada mensaje a la bandeja de Migración con Ayuda y guarda una copia fuera de la web.
declare(strict_types=1);

$DESTINO   = 'migracionconayuda@gmail.com';
$REMITENTE = 'web@migracionconayuda.com';

$isJson = isset($_SERVER['HTTP_ACCEPT']) && strpos($_SERVER['HTTP_ACCEPT'], 'application/json') !== false;
function responder(bool $ok, bool $isJson, string $lang): void {
    if ($isJson) {
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['ok' => $ok]);
    } else {
        $base = $lang === 'en' ? '/en/contact.html' : '/contacto.html';
        header('Location: ' . $base . ($ok ? '?enviado=1' : '?error=1'), true, 303);
    }
    exit;
}

$lang = (($_POST['lang'] ?? 'es') === 'en') ? 'en' : 'es';
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); responder(false, $isJson, $lang); }

// Trampa para robots
if (!empty($_POST['website'])) { responder(true, $isJson, $lang); }

function limpiar(string $k, int $max): string {
    $v = trim((string)($_POST[$k] ?? ''));
    $v = str_replace(["\r", "\0"], '', $v);
    return mb_substr($v, 0, $max);
}
$name    = str_replace("\n", ' ', limpiar('name', 120));
$email   = str_replace("\n", '', limpiar('email', 160));
$phone   = str_replace("\n", ' ', limpiar('phone', 40));
$service = str_replace("\n", ' ', limpiar('service', 80));
$message = limpiar('message', 4000);

if ($name === '' || $message === '' || !filter_var($email, FILTER_VALIDATE_EMAIL) || empty($_POST['privacy'])) {
    responder(false, $isJson, $lang);
}

// Límite simple: 5 envíos por hora por IP
$ip = $_SERVER['REMOTE_ADDR'] ?? '0';
$dir = dirname(__DIR__) . '/mensajes-web';
if (!is_dir($dir)) { @mkdir($dir, 0700, true); }
$rl = $dir . '/.limite-' . md5($ip);
$hits = @json_decode((string)@file_get_contents($rl), true) ?: [];
$hits = array_values(array_filter($hits, fn($t) => $t > time() - 3600));
if (count($hits) >= 5) { responder(false, $isJson, $lang); }
$hits[] = time(); @file_put_contents($rl, json_encode($hits));

// Copia de seguridad (fuera de la carpeta pública)
$fecha = date('Y-m-d H:i:s');
$fp = @fopen($dir . '/contactos.csv', 'a');
if ($fp) {
    fputcsv($fp, [$fecha, $lang, $name, $email, $phone, $service, $message]);
    fclose($fp);
}

$asunto = 'Nuevo mensaje web: ' . $name . ($service ? ' (' . $service . ')' : '');
$cuerpo = "Nuevo mensaje desde migracionconayuda.com\n\n"
        . "Fecha: $fecha\nIdioma: $lang\nNombre: $name\nCorreo: $email\n"
        . "Teléfono / WhatsApp: " . ($phone ?: '-') . "\nInterés: " . ($service ?: '-') . "\n\n"
        . "Mensaje:\n$message\n";
$headers = [
    'From: Migración con Ayuda <' . $REMITENTE . '>',
    'Reply-To: ' . $email,
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=UTF-8',
];
$ok = @mail($DESTINO, '=?UTF-8?B?' . base64_encode($asunto) . '?=', $cuerpo, implode("\r\n", $headers), '-f' . $REMITENTE);

// Si el correo falla pero quedó guardada la copia, igual se considera recibido
responder($ok || $fp !== false, $isJson, $lang);
