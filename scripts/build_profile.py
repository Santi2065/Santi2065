#!/usr/bin/env python3
# Hallmark · genre: editorial · macrostructure: Portfolio Grid · theme: Grid (ultramarine)
#   · tone: austere/technical · enrichment: Tier-B hand-built SVG (kit marks + real data)
#   · nav: none (GitHub chrome) · footer: Ft2 inline single line · motion: none
"""Genera los SVG del README de perfil (versión clara y oscura de cada figura).

Todo el texto se convierte en trazos con HarfBuzz + fontTools, así se ve igual en
cualquier sistema. Los colores se definen como tokens OKLCH y se emiten en hex
(el renderizador de imágenes de GitHub no garantiza oklch()).

Uso:      python3 scripts/build_profile.py assets
Requiere: pip install uharfbuzz fonttools
          Archivo (OFL): ARCHIVO=/ruta/a/Archivo[wdth,wght].ttf
"""
import io
import math
import random
import os
import sys
from collections import defaultdict
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ARCHIVO = Path(os.environ.get("ARCHIVO", "fonts/archivo/Archivo[wdth,wght].ttf"))

# ---------------------------------------------------------------- tokens (OKLCH)

TOKENS = {
    "light": {
        "ink":     (16, 0.010, 255),
        "muted":   (46, 0.012, 255),
        "rule":    (90, 0.006, 255),   # rieles de la grilla
        "hair":    (80, 0.008, 255),   # filetes entre celdas
        "signal":  (45, 0.190, 264),   # ultramar: la única tinta
        "on-plate": (98, 0.005, 255),
        "plate-rule": (53, 0.150, 264),
    },
    "dark": {
        "ink":     (93, 0.006, 255),
        "muted":   (72, 0.012, 255),
        "rule":    (26, 0.012, 255),
        "hair":    (36, 0.012, 255),
        "signal":  (68, 0.150, 264),
        "on-plate": (98, 0.005, 255),
        "plate-rule": (53, 0.150, 264),
    },
}
PLATE = (45, 0.190, 264)  # la placa usa la misma tinta en ambos modos


def oklch_hex(L, C, H):
    """OKLCH (L en %) -> sRGB hex, recortando al gamut."""
    L /= 100
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    out = []
    for c in rgb:
        c = min(max(c, 0.0), 1.0)
        c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        out.append(round(c * 255))
    return "#" + "".join(f"{v:02x}" for v in out)


def palette(theme):
    p = {k: oklch_hex(*v) for k, v in TOKENS[theme].items()}
    p["plate"] = oklch_hex(*PLATE)
    return p


# ---------------------------------------------------------------- tipografía

def ntos(v):
    s = f"{v:.1f}"
    s = s[:-2] if s.endswith(".0") else s
    return "0" if s == "-0" else s


class Face:
    def __init__(self, weight):
        tt = TTFont(str(ARCHIVO))
        inst = instantiateVariableFont(tt, {"wght": weight, "wdth": 100})
        buf = io.BytesIO()
        inst.save(buf)
        data = buf.getvalue()
        self.tt = TTFont(io.BytesIO(data))
        self.upem = self.tt["head"].unitsPerEm
        self.gs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.hb = hb.Font(hb.Face(hb.Blob(data)))

    def shape(self, s, tnum=False):
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True, "tnum": tnum})
        if any(i.codepoint == 0 for i in buf.glyph_infos):
            raise ValueError(f"falta un glifo en {s!r}")
        return buf.glyph_infos, buf.glyph_positions

    def width(self, s, size, track=0.0, tnum=False):
        infos, pos = self.shape(s, tnum)
        return sum(p.x_advance for p in pos) * size / self.upem + track * size * max(len(infos) - 1, 0)

    def path(self, s, size, x, y, anchor="start", track=0.0, tnum=False):
        infos, pos = self.shape(s, tnum)
        k = size / self.upem
        w = self.width(s, size, track, tnum)
        x -= {"start": 0, "middle": w / 2, "end": w}[anchor]
        pen = SVGPathPen(self.gs, ntos=ntos)
        for inf, p in zip(infos, pos):
            self.gs[self.order[inf.codepoint]].draw(
                TransformPen(pen, (k, 0, 0, -k, x + p.x_offset * k, y - p.y_offset * k)))
            x += p.x_advance * k + track * size
        return pen.getCommands(), w


F = {w: Face(w) for w in (400, 500, 600, 800)}

DISPLAY_TRACK = -0.045   # display: minúsculas, Archivo 800
LABEL_TRACK = 0.09       # voz de rótulo: mayúsculas, Archivo 600


def text(s, size, x, y, fill, weight=400, anchor="start", track=0.0, tnum=False):
    d, w = F[weight].path(s, size, x, y, anchor, track, tnum)
    return f'<path d="{d}" fill="{fill}"/>', w


def display(s, size, x, y, fill, anchor="start", tnum=False):
    return text(s, size, x, y, fill, 800, anchor, DISPLAY_TRACK, tnum)


def label(s, size, x, y, fill, anchor="start"):
    return text(s.upper(), size, x, y, fill, 600, anchor, LABEL_TRACK)


def rect(x, y, w, h, fill):
    return f'<rect x="{ntos(x)}" y="{ntos(y)}" width="{ntos(w)}" height="{ntos(h)}" fill="{fill}"/>'


def hline(x1, x2, y, color, w=1):
    return rect(x1, y - w / 2, x2 - x1, w, color)


def vline(x, y1, y2, color, w=1):
    return rect(x - w / 2, y1, w, y2 - y1, color)


def rails(W, H, cols, color, y0=0):
    step = W / cols
    return "".join(vline(min(max(i * step, 0.5), W - 0.5), y0, H, color) for i in range(cols + 1))


def svg(W, H, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'role="img" aria-label="{title}"><title>{title}</title>{body}</svg>\n')


# ---------------------------------------------------------------- cabecera

def masthead(P):
    W, H = 1200, 470
    b = [rails(W, H, 12, P["rule"]), hline(0, W, 1, P["ink"], 2)]
    t, _ = label("Desarrollador de software e IA", 21, 0, 46, P["muted"])
    b.append(t)
    t, _ = label("CABA · Argentina", 21, W, 46, P["muted"], anchor="end")
    b.append(t)
    t, _ = display("santiago", 152, -6, 222, P["ink"])
    b.append(t)
    t, w2 = display("groba alonso", 152, -6, 360, P["ink"])
    b.append(t)
    sq = 0.24 * 152  # cuadrado-punto donde iría el punto final
    b.append(rect(-6 + w2 + 10, 360 - sq, sq, sq, P["signal"]))
    t, _ = text("En producción desde 2020.", 34, 0, 440, P["ink"], 400)
    b.append(t)
    return svg(W, H, "".join(b), "Santiago Groba Alonso — desarrollador de software e IA, en producción desde 2020")


# ---------------------------------------------------------------- pósters (grilla de proyectos)
# Cada póster: rótulo arriba, nombre en display, un objeto del kit en el medio y
# el número clave abajo. Una sola tinta (signal) por póster.

PW, PH = 600, 600


def poster(P, tag, name, obj, big, cap, title, name_size=60, big_size=96):
    b = [rails(PW, PH, 6, P["rule"]), hline(0, PW, 1, P["ink"], 2)]
    t, _ = label(tag, 18, 0, 40, P["muted"])
    b.append(t)
    t, _ = display(name, name_size, -3, 108, P["ink"])
    b.append(t)
    b.append(obj)
    if big:
        t, _ = display(big, big_size, -4, 548, P["ink"], tnum=True)
        b.append(t)
    t, _ = label(cap, 18, 0, 584, P["muted"])
    b.append(t)
    return svg(PW, PH, "".join(b), title)


def p_pdc(P):
    o = []
    cities = [("Bogotá", 226), ("Ipiales", 207), ("Medellín", 150), ("Cartagena", 101), ("Cúcuta", 97)]
    for i, (city, n) in enumerate(cities):
        y = 186 + i * 52
        t, _ = text(city, 24, 0, y + 9, P["ink"], 500)
        o.append(t)
        w = 290 * n / cities[0][1]
        o.append(rect(190, y - 11, w, 22, P["signal"] if i == 0 else P["ink"]))
        t, _ = text(str(n), 24, 190 + w + 12, y + 9, P["muted"], 500, tnum=True)
        o.append(t)
    return poster(P, "En producción · Colombia", "preciodeldolarco", "".join(o), "1.182",
                  "casas de cambio en 62 ciudades",
                  "PrecioDelDolarCo: 1.182 casas de cambio en 62 ciudades; Bogotá 226, Ipiales 207, Medellín 150, Cartagena 101, Cúcuta 97",
                  name_size=54)


def p_llm(P):
    o = []
    for i, (who, sec, num, fill) in enumerate((("antes", 10, "~10 s", P["muted"]), ("ahora", 3, "~3 s", P["signal"]))):
        y = 168 + i * 112
        o.append(rect(0, y, sec * 36, 52, fill))
        t, _ = display(num, 52, sec * 36 + 16, y + 46, P["ink"], tnum=True)
        o.append(t)
        t, _ = label(f"{who} · segundos por respuesta", 16, 0, y + 80, P["muted"])
        o.append(t)
    return poster(P, "En producción · Escribanía", "llm on-premise", "".join(o), "27B",
                  "parámetros · FP8 · 2× RTX 3090",
                  "LLM on-premise: de unos 10 a unos 3 segundos por respuesta; 27B parámetros en FP8 sobre dos RTX 3090")


def p_cot(P):
    o = []
    rows = (("preservar", "viaja todo", 250, P["ink"]), ("comprimir", "un resumen", 120, P["signal"]),
            ("descartar", "solo la respuesta", 40, P["ink"]))
    for i, (word, note, w, fill) in enumerate(rows):
        y = 200 + i * 92
        t, _ = display(word, 44, -2, y, P["ink"])
        o.append(t)
        t, _ = text(note, 19, 0, y + 28, P["muted"], 400)
        o.append(t)
        o.append(rect(PW - 260, y - 30, w, 30, fill))
    return poster(P, "Investigación · UdeSA", "cot-compress", "".join(o), "6",
                  "estrategias para el razonamiento entre turnos",
                  "CoT-Compress: preservar, comprimir o descartar el razonamiento de un LLM entre turnos; 6 estrategias de compresión")


def p_infra(P):
    o = []
    cells = (("Soporte remoto", "de equipos"), ("Redes, backups", "y acceso remoto"),
             ("Renovación", "de hardware"), ("Monitoreo con", "Tactical RMM"))
    top = 160
    o.append(rect(0, top - 1.5, 100, 3, P["signal"]))
    for i, (l1, l2) in enumerate(cells):
        x, y = (i % 2) * 300, top + (i // 2) * 140
        o.append(hline(x, x + 300, y, P["hair"]))
        if i % 2:
            o.append(vline(x, y, y + 140, P["hair"]))
        pad = 16 if i % 2 else 0
        for k, line in enumerate((l1, l2)):
            t, _ = text(line, 26, x + pad, y + 56 + k * 34, P["ink"], 500)
            o.append(t)
    o.append(hline(0, PW, top + 280, P["hair"]))
    return poster(P, "Desde 2020 · CABA", "infraestructura", "".join(o), "2020",
                  "escribanías y pymes",
                  "Infraestructura de escribanías y pymes de CABA desde 2020: soporte, redes, backups, hardware y monitoreo")


def p_derma(P):
    o = []
    s, gap = 64, 18
    for i in range(7):
        x = i * (s + gap)
        o.append(rect(x, 250, s, s, P["signal"] if i == 3 else P["ink"]))
    t, _ = label("7 clases de lesión · 10.015 imágenes", 18, 0, 362, P["muted"])
    o.append(t)
    return poster(P, "Visión artificial · 2026", "dermavision", "".join(o), "0,729",
                  "macro-F1",
                  "DermaVision: clasifica 7 tipos de lesiones de piel sobre 10.015 imágenes; 0,729 de macro-F1")


def p_stereo(P):
    o = []
    obj = (300, 180)
    cams = ((90, 370), (510, 370))
    for cx, cy in cams:
        o.append(f'<line x1="{cx}" y1="{cy}" x2="{obj[0]}" y2="{obj[1]}" stroke="{P["ink"]}" stroke-width="2"/>')
        o.append(rect(cx - 36, cy - 4, 72, 44, P["ink"]))
    o.append(hline(90, 510, 392, P["hair"], 1))
    o.append(f'<circle cx="{obj[0]}" cy="{obj[1]}" r="34" fill="{P["signal"]}"/>')
    t, _ = label("izquierda", 15, 54, 446, P["muted"])
    o.append(t)
    t, _ = label("derecha", 15, 546, 446, P["muted"], anchor="end")
    o.append(t)
    return poster(P, "Visión artificial · 2026", "estéreo 3d", "".join(o), "3,3 M",
                  "puntos · 21 de 21 pares registrados",
                  "Reconstrucción 3D estéreo: 3,3 millones de puntos, 21 de 21 pares registrados")


def p_hex(P):
    o = []
    r = 19
    dx, dy = r * math.sqrt(3), r * 1.5
    n = 7
    chain = {(0, 3), (1, 3), (2, 2), (3, 2), (4, 3), (5, 3), (6, 2)}  # esquema
    for row in range(n):
        for col in range(n):
            cx = 70 + col * dx + row * dx / 2
            cy = 190 + row * dy
            pts = " ".join(f"{ntos(cx + r * math.cos(math.radians(60 * k + 30)))},"
                           f"{ntos(cy + r * math.sin(math.radians(60 * k + 30)))}" for k in range(6))
            filled = (col, row) in chain
            o.append(f'<polygon points="{pts}" fill="{P["signal"] if filled else "none"}" '
                     f'stroke="{P["signal"] if filled else P["hair"]}" stroke-width="1.5"/>')
    t, _ = label("esquema · cadena de borde a borde", 15, 0, 452, P["muted"])
    o.append(t)
    return poster(P, "Fundamentos de IA · 2025", "agente de hex", "".join(o), "18/18",
                  "partidas ganadas a los agentes base",
                  "Agente de Hex con búsqueda alfa-beta: 18 de 18 partidas ganadas a los agentes base")


def p_arm(P):
    o = []
    cw, y, h = PW / 32, 250, 70
    for i in range(32):
        bit = 31 - i
        o.append(rect(i * cw + 1, y, cw - 2, h, P["signal"] if bit >= 21 else P["hair"]))
    for bit, anchor in ((31, "start"), (21, "end"), (0, "end")):
        x = (31 - bit) * cw + (0 if anchor == "start" else cw)
        t, _ = text(str(bit), 20, x, y - 14, P["muted"], 500, anchor=anchor, tnum=True)
        o.append(t)
    t, _ = label("instrucción A64 de 32 bits", 16, 0, y + h + 40, P["muted"])
    o.append(t)
    t, _ = label("bits 31–21: clave de decodificación", 16, 0, y + h + 68, P["signal"])
    o.append(t)
    return poster(P, "Arquitectura · 2025", "simulador armv8", "".join(o), "11/11",
                  "programas iguales a la referencia",
                  "Simulador ARMv8 en C: 11 de 11 programas idénticos al simulador de referencia",
                  name_size=56)


def p_v6(P):
    o = []
    cw, y = 70, 190
    t, _ = label("inodo · i_addr[8]", 16, 0, y - 16, P["muted"])
    o.append(t)
    for i in range(8):
        x = i * (cw + 4)
        o.append(rect(x, y, cw, 54, P["signal"] if i == 7 else P["ink"]))
    for i in range(8):  # cada dirección apunta a un bloque de 256 direcciones
        x = i * (cw + 4) + cw / 2
        o.append(vline(x, y + 54, y + 96, P["hair"], 2))
        for k in range(3):
            o.append(rect(i * (cw + 4) + k * 24, y + 100, 20, 20, P["hair"]))
    t, _ = label("7 indirectos + 1 doble indirecto", 16, 0, y + 170, P["muted"])
    o.append(t)
    return poster(P, "Sistemas operativos · 2025", "unix v6 fs", "".join(o), "12/12",
                  "pruebas idénticas a la referencia",
                  "Lector del file system de Unix V6 en C: salida idéntica a la de referencia en 12 de 12 pruebas")


def p_pozos(P):
    o = []
    x0, x1, y0, y1, split = 0, 580, 160, 410, 300
    o.append(hline(x0, x1, y1, P["hair"], 1))
    q = lambda t: y1 - 240 / (1 + 0.012 * t) ** 1.6  # curva de Arps (esquema)
    hist = " ".join(f"{ntos(t)},{ntos(q(t))}" for t in range(x0, split + 1, 6))
    fore = " ".join(f"{ntos(t)},{ntos(q(t))}" for t in range(split, x1 + 1, 6))
    o.append(f'<polyline points="{hist}" fill="none" stroke="{P["ink"]}" stroke-width="3"/>')
    o.append(f'<polyline points="{fore}" fill="none" stroke="{P["signal"]}" stroke-width="3" stroke-dasharray="10 8"/>')
    o.append(vline(split, y0, y1, P["hair"], 1))
    t, _ = label("histórico", 15, split - 12, y0 + 18, P["muted"], anchor="end")
    o.append(t)
    t, _ = label("60 meses", 15, split + 12, y0 + 18, P["signal"])
    o.append(t)
    t, _ = label("esquema · Arps + LSTM", 15, 0, y1 + 30, P["muted"])
    o.append(t)
    return poster(P, "Ing. de software · 2026", "pozos", "".join(o), "4.929",
                  "pozos con pronóstico a 60 meses",
                  "Plataforma de pozos: pronóstico a 60 meses de 4.929 pozos con un modelo Arps + LSTM")


def p_clear(P):
    o = []
    rnd = random.Random(7)
    for k, (yc, noise, fill, tag) in enumerate(((220, 22, P["ink"], "con ruido"), (360, 0, P["signal"], "limpia"))):
        pts = " ".join(f"{ntos(x)},{ntos(yc - 46 * math.sin(x / 38) + (rnd.uniform(-noise, noise) if noise else 0))}"
                       for x in range(0, PW + 1, 5))
        o.append(f'<polyline points="{pts}" fill="none" stroke="{fill}" stroke-width="{2 if noise else 3}"/>')
        t, _ = label(tag, 15, 0, yc - 64, P["muted"])
        o.append(t)
    t, _ = label("esquema", 15, 0, 444, P["muted"])
    o.append(t)
    return poster(P, "Aprendizaje automático · 2025", "clearwave", "".join(o), "u-net",
                  "autoencoders para quitar ruido de la voz",
                  "ClearWave: elimina el ruido de la voz con autoencoders y una U-Net")


def p_all(P):
    o = []
    # flecha de señalética hecha con rectángulos
    o.append(rect(0, 290, 380, 40, P["ink"]))
    o.append(f'<path d="M360 210L520 310L360 410Z" fill="{P["signal"]}"/>')
    return poster(P, "github.com/Santi2065", "ver todos", "".join(o), "",
                  "los trabajos, con figuras y resultados",
                  "Ver todos los repositorios de Santiago Groba Alonso")


# ---------------------------------------------------------------- herramientas

def tools(P):
    W, H = 1200, 400
    b = [rails(W, H, 12, P["rule"]), hline(0, W, 1, P["ink"], 2), rect(0, 0, 200, 4, P["signal"])]
    rows = (("Lenguajes", "Python · TypeScript · C · C++ · Java"),
            ("IA y ML", "PyTorch · vLLM · llama.cpp · Ollama · Qdrant · MLflow"),
            ("Datos", "PostgreSQL · dbt · Dagster"),
            ("Web", "Next.js · React · FastAPI"),
            ("Infra", "Docker · Linux · AWS · nginx · Prometheus · Grafana · GitHub Actions"),
            ("Idiomas", "español · inglés · francés (básico)"))
    for i, (cat, items) in enumerate(rows):
        y = 70 + i * 60
        t, _ = label(cat, 17, 6, y, P["muted"])
        b.append(t)
        t, _ = text(items, 28, 200, y + 2, P["ink"], 500)
        b.append(t)
        b.append(hline(0, W, y + 24, P["rule"]))
    return svg(W, H, "".join(b), "Herramientas: " + "; ".join(f"{c}: {it}" for c, it in rows))


POSTERS = {"pdc": p_pdc, "llm": p_llm, "cot": p_cot, "infra": p_infra, "derma": p_derma,
           "stereo": p_stereo, "hex": p_hex, "arm": p_arm, "v6": p_v6, "pozos": p_pozos,
           "clear": p_clear, "all": p_all}


# ---------------------------------------------------------------- la placa

def plate(P, dates):
    W, H = 1200, 330
    b = [rect(0, 0, W, H, P["plate"]), rails(W, H, 12, P["plate-rule"])]
    t, _ = display("22", 300, -14, 262, P["on-plate"], tnum=True)
    b.append(t)
    t, _ = display("trabajos documentados", 50, 400, 92, P["on-plate"])
    b.append(t)
    t, _ = text("de mi primera web (2022) a visión artificial (2026)", 25, 402, 134, P["on-plate"], 400)
    b.append(t)
    # línea de tiempo con las fechas reales; mismo mes = se apilan hacia arriba
    x0, x1, y = 400, 1180, 268
    span = (2022.0, 2027.0)
    fx = lambda v: x0 + (v - span[0]) / (span[1] - span[0]) * (x1 - x0)
    b.append(hline(x0, x1, y, P["on-plate"], 2))
    for yr in range(2022, 2028):
        b.append(vline(fx(yr), y - 8, y + 8, P["on-plate"], 2))
    for yr in range(2022, 2027):
        t, _ = label(str(yr), 16, fx(yr + 0.5), y + 40, P["on-plate"], anchor="middle")
        b.append(t)
    stack = defaultdict(int)
    for d in sorted(dates):
        yr, mo, dy = (int(v) for v in d.split("-"))
        v = yr + (mo - 1 + (dy - 1) / 31) / 12
        k = stack[d[:7]]
        stack[d[:7]] += 1
        b.append(f'<circle cx="{ntos(fx(v))}" cy="{ntos(y - 22 - k * 17)}" r="6.5" fill="{P["on-plate"]}"/>')
    return svg(W, H, "".join(b), "22 trabajos documentados entre 2022 y 2026, uno por punto en la línea de tiempo")


# ---------------------------------------------------------------- main

# Fechas de los 22 repos públicos de la trayectoria (kit/milestones.json sin el privado vacío).
DATES = ["2022-05-27", "2022-11-30", "2023-04-02", "2023-05-23", "2023-07-01", "2023-11-05",
         "2023-11-12", "2024-06-25", "2024-09-09", "2024-10-10", "2025-03-31", "2025-04-15",
         "2025-04-15", "2025-05-14", "2025-05-25", "2025-05-31", "2025-06-15", "2025-06-22",
         "2025-06-25", "2025-08-29", "2025-11-17", "2026-05-22"]


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    builders = {"masthead": masthead, "plate": lambda P: plate(P, DATES), "tools": tools,
                **{f"poster-{k}": fn for k, fn in POSTERS.items()}}
    for name, fn in builders.items():
        for theme in ("light", "dark"):
            path = out / f"{name}-{theme}.svg"
            path.write_text(fn(palette(theme)), encoding="utf-8")
            print(f"{path.name}: {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    assert len(DATES) == 22
    main(sys.argv[1])
