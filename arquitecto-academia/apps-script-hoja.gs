// Pegar en la hoja: Extensiones > Apps Script. Luego Implementar > Nueva implementación > Aplicación web
// (Ejecutar como: yo. Quién tiene acceso: cualquier persona). Copiar la URL que termina en /exec.
const CLAVE = 'CAMBIA-ESTA-CLAVE'; // misma que 'sheets_key' en api/config.php
const COLUMNAS = ['fecha','nombre','email','whatsapp','tema','audiencia','transformacion','profesion','experiencia','nivel','tiempo','aprende','frase_final','forma_ensenar','sensacion','meta','arquetipo','formato','plano_url','origen','utm'];

function doPost(e) {
  const d = JSON.parse(e.postData.contents);
  if (d.clave !== CLAVE) return ContentService.createTextOutput('no').setMimeType(ContentService.MimeType.TEXT);
  const hoja = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  const fila = COLUMNAS.map(c => {
    const v = d[c];
    return (v && typeof v === 'object') ? JSON.stringify(v) : (v == null ? '' : String(v));
  });
  hoja.appendRow(fila);
  return ContentService.createTextOutput('ok').setMimeType(ContentService.MimeType.TEXT);
}
