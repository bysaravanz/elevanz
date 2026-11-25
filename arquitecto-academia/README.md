# Arquitecto de Academia

Sitio estático servido en https://academia.saravanz.com (Hostinger, carpeta `public_html/academia`).

- `index.html`: la herramienta completa. El logo se carga desde `logo-saravanz.png`.
- `api/lead.php`: recibe el lead y lo reenvía al webhook de GoHighLevel.
- `api/config.php`: contiene credenciales, vive solo en el servidor. Ver `config.example.php`.
