# Arquitecto de Academia

Sitio estático servido en https://academia.saravanz.com (Hostinger, carpeta `public_html/academia`).

- `index.html`: la herramienta completa. El logo va incrustado en base64 en la versión publicada; aquí está el marcador `__LOGO_DATA_URI__`. No se debe volver a subir este archivo sin reponer el logo.
- `api/lead.php`: recibe el lead y lo reenvía al webhook de GoHighLevel.
- `api/config.php`: contiene credenciales, vive solo en el servidor. Ver `config.example.php`.
