#!/usr/bin/env python3
"""Editor automático de reels.

Uso:
    python editar.py                      # edita todos los videos de entrada/
    python editar.py entrada/mi_video.mp4 # edita uno
    python editar.py mi_video.mp4 --musica musica/cancion.mp3

Pasos: transcribe, corta silencios, genera subtítulos, anima, mezcla música
y exporta un MP4 9:16 en salida/.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
EXT_VIDEO = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}
EXT_AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}

STOPWORDS = set("""a al algo ante con contra cual cuando de del desde donde e el ella ellas ello ellos en entre era
eran es esa ese eso esta estaba estan estas este esto estos fue ha han has hay he la las le les lo los me mi mis mas
muy ni no nos o para pero por porque que quien se ser si sin so sobre son su sus te ti tu tus un una uno unas unos y ya yo
como cada hasta tan tanto then the and of to in is it that this for with are was be""".split())


# ---------------------------------------------------------------- utilidades

def correr(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def fallar(msg):
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def hex_a_ass(hex_color, alpha=0):
    """#RRGGBB -> &HAABBGGRR (formato de color de ASS)."""
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def hex_a_ffmpeg(hex_color):
    return "0x" + hex_color.lstrip("#")


def quitar_acentos(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def limpiar_palabra(s):
    return re.sub(r"[^\w]", "", quitar_acentos(s).lower())


def slug(s):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", quitar_acentos(s)).strip("_") or "video"


# -------------------------------------------------------------------- sonda

def sondear(video):
    r = correr(["ffprobe", "-v", "error", "-show_entries",
                "format=duration:stream=codec_type,width,height", "-of", "json", str(video)])
    if r.returncode != 0:
        fallar(f"No pude leer {video}. ¿Es un video válido?\n{r.stderr}")
    info = json.loads(r.stdout)
    dur = float(info["format"]["duration"])
    tipos = [s["codec_type"] for s in info["streams"]]
    if "audio" not in tipos:
        fallar("El video no tiene audio. Necesito tu voz para transcribir y cortar silencios.")
    return dur


# ------------------------------------------------------------ transcripción

def transcribir(video, modelo, idioma, destino):
    """Devuelve lista de {texto, inicio, fin}. Guarda el resultado para no repetir."""
    if destino.exists():
        print(f"  Uso la transcripción guardada: {destino.name}")
        return cargar_palabras(destino)
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        fallar("Falta faster-whisper. Corre: pip install -r requirements.txt")
    print(f"  Transcribiendo con el modelo '{modelo}' (la primera vez descarga el modelo)...")
    try:
        m = WhisperModel(modelo, device="cpu", compute_type="int8")
        segs, _ = m.transcribe(str(video), language=idioma, word_timestamps=True,
                               vad_filter=True, condition_on_previous_text=False)
        palabras = []
        for s in segs:
            for w in s.words or []:
                t = w.word.strip()
                if t:
                    palabras.append({"texto": t, "inicio": round(w.start, 3), "fin": round(w.end, 3)})
    except Exception as e:  # modelo no descargable, sin red, etc.
        fallar(f"No pude transcribir: {e}\n"
               "Si no hay internet para bajar el modelo, pasa una transcripción con --transcripcion.")
    destino.write_text(json.dumps({"idioma": idioma, "palabras": palabras}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    return palabras


def cargar_palabras(ruta):
    data = json.loads(Path(ruta).read_text(encoding="utf-8"))
    pal = data["palabras"] if isinstance(data, dict) else data
    return [{"texto": p["texto"], "inicio": float(p["inicio"]), "fin": float(p["fin"])} for p in pal]


# ---------------------------------------------------------- corte de silencios

def detectar_silencios(video, db, dur):
    r = correr(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video), "-vn",
                "-af", f"silencedetect=noise={db}dB:d=0.25", "-f", "null", "-"])
    inicios = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    fines = [float(x) for x in re.findall(r"silence_end: (-?[\d.]+)", r.stderr)]
    sil = []
    for i, s in enumerate(inicios):
        e = fines[i] if i < len(fines) else dur
        sil.append((max(0.0, s), min(dur, e)))
    return sil


def complemento(intervalos, dur):
    res, cur = [], 0.0
    for s, e in sorted(intervalos):
        if s > cur:
            res.append((cur, s))
        cur = max(cur, e)
    if cur < dur:
        res.append((cur, dur))
    return res


def unir(intervalos, hueco):
    out = []
    for s, e in sorted(intervalos):
        if out and s - out[-1][1] <= hueco:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def calcular_segmentos(video, dur, palabras, cfg):
    sil = detectar_silencios(video, cfg["umbral_silencio_db"], dur)
    habla = complemento(sil, dur)
    # las palabras transcritas nunca se pueden cortar
    habla += [(p["inicio"], p["fin"]) for p in palabras]
    col = cfg["colchon_seg"]
    habla = [(max(0.0, s - col), min(dur, e + col)) for s, e in habla if e > s]
    segs = unir(habla, cfg["pausa_maxima_seg"])
    minimo = cfg["segmento_minimo_seg"]
    segs = [(s, e) for s, e in segs
            if e - s >= minimo or any(s <= p["inicio"] < e for p in palabras)]
    if not segs:
        fallar("No encontré voz en el video.")
    return segs


def mapear_tiempos(palabras, segs):
    """Pasa los tiempos de las palabras a la línea de tiempo del video ya cortado."""
    inicios_salida, acc = [], 0.0
    for s, e in segs:
        inicios_salida.append(acc)
        acc += e - s
    res = []
    for p in palabras:
        for (s, e), o in zip(segs, inicios_salida):
            if s - 1e-3 <= p["inicio"] < e:
                ini = o + (p["inicio"] - s)
                fin = o + (min(p["fin"], e) - s)
                res.append({"texto": p["texto"], "inicio": ini, "fin": max(fin, ini + 0.08)})
                break
    return res, acc


# ---------------------------------------------------------------- subtítulos

def elegir_clave(palabras_bloque, siempre):
    mejor, mejor_score = None, 0
    for i, p in enumerate(palabras_bloque):
        w = limpiar_palabra(p["texto"])
        if not w:
            continue
        if w in siempre:
            return i
        score = len(w)
        if w in STOPWORDS:
            continue
        if any(c.isdigit() for c in w):
            score += 6
        if score > mejor_score:
            mejor, mejor_score = i, score
    return mejor


def armar_bloques(pal, cfg):
    sub = cfg["subtitulos"]
    maxp = sub["palabras_por_bloque"]
    hueco = sub["pausa_para_cortar_bloque_seg"]
    bloques, cur = [], []
    for p in pal:
        if cur and p["inicio"] - cur[-1]["fin"] > hueco:
            bloques.append(cur)
            cur = []
        cur.append(p)
        fin_frase = cur[-1]["texto"][-1] in ".?!…"
        coma = cur[-1]["texto"][-1] in ",;:" and len(cur) >= 2
        if len(cur) >= maxp or fin_frase or coma:
            bloques.append(cur)
            cur = []
    if cur:
        bloques.append(cur)
    return bloques


def escapar_ass(t):
    return t.replace("\\", "").replace("{", "(").replace("}", ")")


def texto_bloque(b, cfg, clave):
    tip = cfg["tipografia"]
    c = cfg["colores"]
    amarillo = "&H" + hex_a_ass(c["resalte"])[4:] + "&"
    blanco = "&H" + hex_a_ass(c["texto"])[4:] + "&"
    textos = []
    for p in b:
        t = escapar_ass(p["texto"])
        textos.append(t.upper() if tip["mayusculas"] else t)
    # salto de línea si el bloque es largo
    total = sum(len(t) for t in textos) + len(textos) - 1
    corte = None
    if total > cfg["subtitulos"]["max_caracteres_linea"] and len(textos) >= 2:
        mejor = None
        for i in range(1, len(textos)):
            izq = sum(len(t) for t in textos[:i]) + i - 1
            dif = abs(izq - (total - izq))
            if mejor is None or dif < mejor:
                mejor, corte = dif, i
    partes = []
    for i, t in enumerate(textos):
        if i == clave:
            t = "{\\c%s}%s{\\c%s}" % (amarillo, t, blanco)
        partes.append(t)
        if corte is not None and i == corte - 1:
            partes.append("\\N")
        elif i < len(textos) - 1:
            partes.append(" ")
    return "".join(partes).replace(" \\N ", "\\N").replace(" \\N", "\\N")


def tiempo_ass(t):
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def generar_ass(pal, cfg, ruta):
    ex, tip, col = cfg["exportacion"], cfg["tipografia"], cfg["colores"]
    y = int(ex["alto"] * cfg["subtitulos"]["posicion_vertical_pct"])
    x = ex["ancho"] // 2
    siempre = {limpiar_palabra(w) for w in cfg["subtitulos"]["palabras_clave_siempre"]}
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {ex['ancho']}
PlayResY: {ex['alto']}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Reel,{tip['familia']},{tip['tamano']},{hex_a_ass(col['texto'])},{hex_a_ass(col['texto'])},{hex_a_ass(col['contorno'])},&H80000000,0,0,0,0,100,100,0,0,1,{tip['contorno_px']},{tip['sombra_px']},5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    bloques = armar_bloques(pal, cfg)
    lineas = []
    for i, b in enumerate(bloques):
        ini = b[0]["inicio"]
        sig = bloques[i + 1][0]["inicio"] if i + 1 < len(bloques) else None
        fin = b[-1]["fin"] + 0.2
        if sig is not None:
            fin = min(fin, sig)
        clave = elegir_clave(b, siempre)
        txt = texto_bloque(b, cfg, clave)
        # animación de entrada: aparece un poco chico y "rebota" a su tamaño
        anim = "\\fscx80\\fscy80\\t(0,90,\\fscx108\\fscy108)\\t(90,170,\\fscx100\\fscy100)"
        lineas.append(f"Dialogue: 0,{tiempo_ass(ini)},{tiempo_ass(fin)},Reel,,0,0,0,,"
                      f"{{\\an5\\pos({x},{y}){anim}}}{txt}")
    Path(ruta).write_text(cab + "\n".join(lineas) + "\n", encoding="utf-8")
    return len(bloques)


# ------------------------------------------------------------ filtros ffmpeg

def construir_filtros(segs, total, cfg, ass_rel, fontsdir_rel, musica):
    ex, an, au = cfg["exportacion"], cfg["animacion"], cfg["audio"]
    W, H, fps = ex["ancho"], ex["alto"], ex["fps"]
    n = len(segs)
    f = []
    f.append(f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},"
             f"split={n}" + "".join(f"[s{i}]" for i in range(n)))
    f.append(f"[0:a]aresample=48000,asplit={n}" + "".join(f"[a{i}]" for i in range(n)))
    fy = an["zoom_foco_vertical"]
    flashes = []
    acc = 0.0
    for i, (s, e) in enumerate(segs):
        d = e - s
        if an["zoom_alterno"]:
            z0, z1 = an["zoom_cerrado"] if i % 2 else an["zoom_amplio"]
        else:
            z0, z1 = 1.0, 1.0
        z = f"({z0}+({z1}-{z0})*t/{d:.4f})"
        # los frames del segmento empiezan en t=0 gracias a setpts
        f.append(f"[s{i}]trim=start={s:.4f}:end={e:.4f},setpts=PTS-STARTPTS,"
                 f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame,"
                 f"crop={W}:{H}:x='(in_w-{W})/2':y='(in_h-{H})*{fy}':exact=1,setsar=1[v{i}]")
        fd = min(0.01, d / 4)
        f.append(f"[a{i}]atrim=start={s:.4f}:end={e:.4f},asetpts=PTS-STARTPTS,"
                 f"afade=t=in:d={fd:.3f},afade=t=out:st={d - fd:.4f}:d={fd:.3f}[x{i}]")
        if i > 0 and an["flash_cada_n_cortes"] and i % an["flash_cada_n_cortes"] == 0:
            flashes.append(acc)
        acc += d
    f.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vc]")
    f.append("".join(f"[x{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[voz]")

    # video: flash en algunos cortes, subtítulos, fundidos
    cadena_v = "[vc]"
    if flashes:
        h = an["flash_duracion_seg"]
        pulsos = "+".join(f"max(0,1-abs(t-{t:.3f})/{h})" for t in flashes)
        cadena_v += f"eq=brightness='{an['flash_intensidad']}*min(1,{pulsos})':eval=frame,"
    cadena_v += f"ass=filename='{ass_rel}':fontsdir='{fontsdir_rel}',"
    fi, fo = an["fade_entrada_seg"], an["fade_salida_seg"]
    cadena_v += f"fade=t=in:st=0:d={fi},fade=t=out:st={max(0, total - fo):.3f}:d={fo},format=yuv420p[vout]"
    f.append(cadena_v)

    # audio: voz + música baja con ducking
    lufs = au["volumen_final_lufs"]
    if musica:
        f.append(f"[1:a]aresample=48000,aloop=loop=-1:size=2147483647,atrim=0:{total:.3f},"
                 f"volume={au['volumen_musica']},afade=t=in:d=1,afade=t=out:st={max(0, total - 1.5):.3f}:d=1.5[mus]")
        if au["bajar_musica_cuando_hablo"]:
            f.append("[voz]asplit=2[voz1][voz2]")
            f.append("[mus][voz2]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=400[musd]")
            f.append(f"[voz1][musd]amix=inputs=2:duration=first:normalize=0,loudnorm=I={lufs}:TP=-1.5:LRA=11,aformat=channel_layouts=stereo[aout]")
        else:
            f.append(f"[voz][mus]amix=inputs=2:duration=first:normalize=0,loudnorm=I={lufs}:TP=-1.5:LRA=11,aformat=channel_layouts=stereo[aout]")
    else:
        f.append(f"[voz]loudnorm=I={lufs}:TP=-1.5:LRA=11,aformat=channel_layouts=stereo[aout]")
    return ";\n".join(f)


# ------------------------------------------------------------------ proceso

def buscar_musica(arg):
    if arg:
        p = Path(arg)
        if not p.exists():
            p = RAIZ / "musica" / arg
        if not p.exists():
            fallar(f"No encuentro la música: {arg}")
        return p.resolve()
    cand = sorted(p for p in (RAIZ / "musica").glob("*") if p.suffix.lower() in EXT_AUDIO)
    return cand[0].resolve() if cand else None


def editar(video, args, cfg):
    video = Path(video)
    if not video.exists():
        alt = RAIZ / "entrada" / video.name
        video = alt if alt.exists() else video
    if not video.exists():
        fallar(f"No encuentro el video: {video}")
    video = video.resolve()
    nombre = slug(video.stem)
    print(f"\n=== {video.name} ===")
    dur = sondear(video)
    print(f"  Duración original: {dur:.1f}s")

    salida_dir = RAIZ / "salida"
    salida_dir.mkdir(exist_ok=True)
    trans = Path(args.transcripcion) if args.transcripcion else salida_dir / f"{nombre}.palabras.json"
    if args.transcripcion:
        palabras = cargar_palabras(trans)
    else:
        palabras = transcribir(video, args.modelo, args.idioma, trans)
    print(f"  Palabras transcritas: {len(palabras)}")

    segs = calcular_segmentos(video, dur, palabras, cfg["cortes"])
    pal_sal, total = mapear_tiempos(palabras, segs)
    print(f"  Cortes: {len(segs)} segmentos, {dur:.1f}s -> {total:.1f}s (quité {dur - total:.1f}s)")

    ass = salida_dir / f".{nombre}.ass"
    nb = generar_ass(pal_sal, cfg, ass)
    print(f"  Subtítulos: {nb} bloques")

    musica = None if args.sin_musica else buscar_musica(args.musica)
    print(f"  Música: {musica.name if musica else 'ninguna (pon un archivo en musica/ para agregarla)'}")

    fontsdir = Path(cfg["tipografia"]["archivo"]).parent
    grafo = construir_filtros(segs, total, cfg, ass.relative_to(RAIZ).as_posix(), fontsdir.as_posix(), musica)
    guion = salida_dir / f".{nombre}.filtros.txt"
    guion.write_text(grafo, encoding="utf-8")

    destino = salida_dir / f"{nombre}_editado.mp4"
    ex = cfg["exportacion"]
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(video)]
    if musica:
        cmd += ["-i", str(musica)]
    cmd += ["-filter_complex_script", str(guion), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", ex["preset"], "-crf", str(ex["crf"]),
            "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(ex["fps"]),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
            "-t", f"{total:.3f}", str(destino)]
    print("  Renderizando...")
    r = subprocess.run(cmd, cwd=RAIZ)
    if r.returncode != 0:
        fallar("ffmpeg falló. El filtro quedó guardado en " + str(guion))
    if not args.conservar_temporales:
        ass.unlink(missing_ok=True)
        guion.unlink(missing_ok=True)
    print(f"  Listo: {destino.relative_to(RAIZ)}")
    return destino


def main():
    ap = argparse.ArgumentParser(description="Edita reels automáticamente.")
    ap.add_argument("video", nargs="*", help="video(s) a editar; sin esto procesa todo entrada/")
    ap.add_argument("--musica", help="archivo de música (por defecto, el primero de musica/)")
    ap.add_argument("--sin-musica", action="store_true")
    ap.add_argument("--modelo", default="small", help="modelo Whisper: tiny, base, small, medium (default small)")
    ap.add_argument("--idioma", default="es")
    ap.add_argument("--transcripcion", help="JSON con palabras y tiempos (omite Whisper)")
    ap.add_argument("--diseno", default=str(RAIZ / "design-system.json"))
    ap.add_argument("--conservar-temporales", action="store_true")
    args = ap.parse_args()

    for exe in ("ffmpeg", "ffprobe"):
        if not shutil.which(exe):
            fallar(f"No encuentro {exe}. Instálalo (ver README.md).")
    cfg = json.loads(Path(args.diseno).read_text(encoding="utf-8"))
    if not (RAIZ / cfg["tipografia"]["archivo"]).exists():
        fallar(f"No encuentro la tipografía {cfg['tipografia']['archivo']}")

    videos = args.video or sorted(p for p in (RAIZ / "entrada").glob("*") if p.suffix.lower() in EXT_VIDEO)
    if not videos:
        fallar("No hay videos. Deja uno en la carpeta entrada/.")
    for v in videos:
        editar(v, args, cfg)


if __name__ == "__main__":
    main()
