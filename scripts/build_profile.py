#!/usr/bin/env python3
# Hallmark · genre: editorial · macrostructure: Feature Stack (por capacidades) · motion: grow · load · pop · ticker · theme: Grid (ultramarine)
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
        "numeral": (94, 0.010, 255),   # numeral recortado de las cabeceras
        "signal":  (45, 0.190, 264),   # ultramar: la única tinta
        "on-plate": (98, 0.005, 255),
        "plate-rule": (53, 0.150, 264),
    },
    "dark": {
        "ink":     (93, 0.006, 255),
        "muted":   (72, 0.012, 255),
        "rule":    (26, 0.012, 255),
        "hair":    (36, 0.012, 255),
        "numeral": (22, 0.016, 255),
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


EASE_OUT = "cubic-bezier(.16,1,.3,1)"
MOTION = (f".grow{{transform-box:fill-box;transform-origin:0 50%;animation:grow .9s {EASE_OUT} both}}"
          "@keyframes grow{from{transform:scaleX(0)}}"
          f".pop{{transform-box:fill-box;transform-origin:50% 50%;animation:pop .45s {EASE_OUT} both}}"
          "@keyframes pop{from{opacity:0;transform:scale(.3)}}"
          ".load-a,.load-b{transform-box:fill-box;transform-origin:0 50%;animation:4.5s linear infinite}"
          ".load-a{animation-name:loadA}.load-b{animation-name:loadB}"
          # tiempo real a escala: ~10 s y ~3 s se llenan en 3 s y 0,9 s
          "@keyframes loadA{0%{transform:scaleX(0)}66.7%,100%{transform:scaleX(1)}}"
          "@keyframes loadB{0%{transform:scaleX(0)}20%,100%{transform:scaleX(1)}}"
          "@media (prefers-reduced-motion:reduce){*{animation:none!important}}")


def svg(W, H, body, title, css=""):
    style = f"<style>{MOTION}{css}</style>" if "class=" in body else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'role="img" aria-label="{title}"><title>{title}</title>{style}{body}</svg>\n')


def anim(x, y, w, h, fill, cls, delay=0.0):
    d = f' style="animation-delay:{delay:.2f}s"' if delay else ""
    return (f'<rect class="{cls}"{d} x="{ntos(x)}" y="{ntos(y)}" width="{ntos(w)}" '
            f'height="{ntos(h)}" fill="{fill}"/>')


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
        o.append(anim(190, y - 11, w, 22, P["signal"] if i == 0 else P["ink"], "grow", 0.15 + i * 0.08))
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
        o.append(rect(0, y, sec * 36, 52, P["hair"]))
        o.append(anim(0, y, sec * 36, 52, fill, "load-a" if i == 0 else "load-b"))
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
        o.append(anim(PW - 260, y - 30, w, 30, fill, "grow", 0.15 + i * 0.1))
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


# ---------------------------------------------------------------- cinta de herramientas

TOOLS = ["Python", "TypeScript", "C", "C++", "Java", "PyTorch", "vLLM", "llama.cpp", "Ollama", "Qdrant",
         "MLflow", "PostgreSQL", "dbt", "Dagster", "Next.js", "React", "FastAPI", "Docker", "Linux", "AWS",
         "nginx", "Prometheus", "Grafana", "GitHub Actions", "español", "inglés", "francés (básico)"]


def ticker(P):
    W, H, size, gap, sq = 1200, 76, 28, 34, 9
    items, x = [], 0.0
    for name in TOOLS:
        t, w = text(name, size, x, 48, P["ink"], 500)
        items.append(t)
        x += w + gap
        items.append(rect(x - gap / 2 - sq / 2, 48 - 10 - sq / 2, sq, sq, P["signal"]))
    L = x
    copy = "".join(items)
    body = (f'<clipPath id="band"><rect width="{W}" height="{H}"/></clipPath>'
            + hline(0, W, 1, P["ink"], 2) + hline(0, W, H - 1, P["rule"], 2)
            + f'<g clip-path="url(#band)"><g class="tick">{copy}'
            f'<g transform="translate({ntos(L)} 0)">{copy}</g></g></g>')
    css = (f".tick{{animation:tick {L / 28:.0f}s linear infinite}}"
           f"@keyframes tick{{to{{transform:translateX(-{ntos(L)}px)}}}}")
    return svg(W, H, body, "Herramientas e idiomas: " + ", ".join(TOOLS), css)


POSTERS = {"pdc": p_pdc, "infra": p_infra, "llm": p_llm, "cot": p_cot}


# ---------------------------------------------------------------- cabeceras de capacidad

CAPACIDADES = {
    1: ("llevo software", "a producción"),
    2: ("ia que corre en", "casa del cliente"),
    3: ("bases sólidas:", "sistemas e ia"),
}


def head(P, n):
    """Título de una capacidad; el número es un objeto recortado, no un rótulo."""
    W, H = 1200, 220
    b = [rails(W, H, 12, P["rule"]), hline(0, W, 1, P["ink"], 2)]
    t, _ = display(str(n), 360, W + 12, H + 84, P["numeral"], anchor="end", tnum=True)
    b.append(t)
    l1, l2 = CAPACIDADES[n]
    t, _ = display(l1, 76, -4, 100, P["ink"])
    b.append(t)
    t, w2 = display(l2, 76, -4, 186, P["ink"])
    b.append(t)
    sq = 0.24 * 76
    b.append(rect(-4 + w2 + 7, 186 - sq, sq, sq, P["signal"]))
    return svg(W, H, "".join(b), f"{l1} {l2}")


# ---------------------------------------------------------------- la placa

def plate(P, dates):
    W, H = 1200, 380
    b = [rect(0, 0, W, H, P["plate"]), rails(W, H, 12, P["plate-rule"])]
    t, _ = display("22", 300, -14, 300, P["on-plate"], tnum=True)
    b.append(t)
    t, _ = display("trabajos documentados", 50, 400, 92, P["on-plate"])
    b.append(t)
    t, _ = text("de mi primera web (2022) a visión artificial (2026)", 25, 402, 134, P["on-plate"], 400)
    b.append(t)
    for k, (num, what) in enumerate((("11/11", "simulador armv8"), ("12/12", "unix v6 fs"), ("18/18", "agente de hex"))):
        x = 402 + k * 260
        t, _ = display(num, 46, x - 2, 206, P["on-plate"], tnum=True)
        b.append(t)
        t, _ = label(what, 15, x, 232, P["on-plate"])
        b.append(t)
    # línea de tiempo con las fechas reales; mismo mes = se apilan hacia arriba
    x0, x1, y = 400, 1180, 318
    span = (2022.0, 2027.0)
    fx = lambda v: x0 + (v - span[0]) / (span[1] - span[0]) * (x1 - x0)
    b.append(hline(x0, x1, y, P["on-plate"], 2))
    for yr in range(2022, 2028):
        b.append(vline(fx(yr), y - 8, y + 8, P["on-plate"], 2))
    for yr in range(2022, 2027):
        t, _ = label(str(yr), 16, fx(yr + 0.5), y + 40, P["on-plate"], anchor="middle")
        b.append(t)
    stack = defaultdict(int)
    for i, d in enumerate(sorted(dates)):
        yr, mo, dy = (int(v) for v in d.split("-"))
        v = yr + (mo - 1 + (dy - 1) / 31) / 12
        k = stack[d[:7]]
        stack[d[:7]] += 1
        b.append(f'<circle class="pop" style="animation-delay:{0.2 + i * 0.08:.2f}s" cx="{ntos(fx(v))}" '
                 f'cy="{ntos(y - 22 - k * 17)}" r="6.5" fill="{P["on-plate"]}"/>')
    return svg(W, H, "".join(b), "22 trabajos documentados entre 2022 y 2026; entre ellos un simulador ARMv8 "
               "(11 de 11 programas), un lector de Unix V6 (12 de 12 pruebas) y un agente de Hex (18 de 18 partidas)")


# ---------------------------------------------------------------- main

# Fechas de los 22 repos públicos de la trayectoria (kit/milestones.json sin el privado vacío).
DATES = ["2022-05-27", "2022-11-30", "2023-04-02", "2023-05-23", "2023-07-01", "2023-11-05",
         "2023-11-12", "2024-06-25", "2024-09-09", "2024-10-10", "2025-03-31", "2025-04-15",
         "2025-04-15", "2025-05-14", "2025-05-25", "2025-05-31", "2025-06-15", "2025-06-22",
         "2025-06-25", "2025-08-29", "2025-11-17", "2026-05-22"]


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    builders = {"masthead": masthead, "plate": lambda P: plate(P, DATES), "tools": ticker,
                **{f"head-{n}": (lambda P, n=n: head(P, n)) for n in CAPACIDADES},
                **{f"poster-{k}": fn for k, fn in POSTERS.items()}}
    for name, fn in builders.items():
        for theme in ("light", "dark"):
            path = out / f"{name}-{theme}.svg"
            path.write_text(fn(palette(theme)), encoding="utf-8")
            print(f"{path.name}: {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    assert len(DATES) == 22
    main(sys.argv[1])
