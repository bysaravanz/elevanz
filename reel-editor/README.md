# Editor de reels

Toma un video vertical donde hablas a cámara y devuelve un MP4 9:16 listo para subir a Instagram.

## Qué hace

1. Transcribe tu voz con Whisper (en español por defecto).
2. Corta silencios y pausas largas. Las pausas cortas de respiración se quedan.
3. Pone subtítulos grandes, de 2 a 3 palabras por bloque, con una palabra clave en amarillo por bloque.
4. Anima: zoom que alterna entre plano amplio y cerrado en cada corte, flash blanco en algunos cortes, subtítulos que entran con rebote, fundido al inicio y al final.
5. Mezcla música de fondo baja. La música baja sola mientras hablas.
6. Exporta 1080x1920, H.264, AAC, 30 fps, con el volumen normalizado a -14 LUFS.

## Carpetas

| Carpeta | Para qué |
|---|---|
| `entrada/` | Aquí dejas tus videos |
| `musica/` | Aquí dejas tus canciones. Se usa la primera por orden alfabético |
| `salida/` | Aquí aparece el video editado (`nombre_editado.mp4`) y la transcripción (`nombre.palabras.json`) |
| `fonts/` | Tipografía de los subtítulos |
| `design-system.json` | Colores, fuente, tamaños y ritmo de la animación |

## Instalación (una sola vez)

Necesitas ffmpeg y Python 3.9 o superior.

```bash
# Mac
brew install ffmpeg
# Ubuntu o Debian
sudo apt install ffmpeg
# Windows
winget install ffmpeg
```

```bash
cd reel-editor
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

La primera vez que transcribes, faster-whisper descarga el modelo (unos 500 MB para `small`). Necesita acceso a huggingface.co.

## Uso

```bash
python editar.py                          # edita todo lo que haya en entrada/
python editar.py entrada/mi_video.mp4     # edita uno
python editar.py mi_video.mp4 --musica musica/cancion.mp3
python editar.py mi_video.mp4 --sin-musica
python editar.py mi_video.mp4 --modelo medium   # más preciso, más lento
```

## Corregir una palabra mal transcrita

Abre `salida/nombre.palabras.json`, corrige el texto de la palabra y vuelve a correr el comando con
`--transcripcion salida/nombre.palabras.json`. No transcribe de nuevo, solo re-renderiza.

## Cambiar el look

Todo está en `design-system.json`. Los más usados:

- `colores.resalte`: color de la palabra clave.
- `tipografia.tamano` y `tipografia.archivo`: tamaño y fuente. Para otra fuente, copia el `.ttf` a `fonts/` y cambia `archivo` y `familia`.
- `subtitulos.palabras_clave_siempre`: lista de palabras que siempre van en amarillo (por ejemplo, el nombre de tu marca).
- `cortes.pausa_maxima_seg`: pausas más largas que esto se cortan. Súbelo para un ritmo más pausado.
- `animacion.flash_cada_n_cortes`: pon `0` para quitar los flashes.
- `audio.volumen_musica`: 0.12 es bajito. Súbelo a 0.2 si lo quieres más presente.

## Cómo elige la palabra clave

Dentro de cada bloque descarta artículos, preposiciones y conectores, y se queda con la palabra más larga. Los números pesan más. Las palabras de `palabras_clave_siempre` tienen prioridad.

## Licencia de la fuente

Poppins está bajo SIL Open Font License (ver `fonts/OFL.txt`).
