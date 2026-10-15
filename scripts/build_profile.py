#!/usr/bin/env python3
# Hallmark · genre: editorial · macrostructure: Split Studio · theme: Grid (ultramarine)
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
        "faint":   (93, 0.008, 255),   # barras secundarias, numeral de fondo
        "signal":  (45, 0.190, 264),   # ultramar: la única tinta
        "on-plate": (99, 0.003, 255),
        "plate-rule": (53, 0.150, 264),
    },
    "dark": {
        "ink":     (93, 0.006, 255),
        "muted":   (72, 0.012, 255),
        "rule":    (26, 0.012, 255),
        "hair":    (36, 0.012, 255),
        "faint":   (30, 0.014, 255),
        "signal":  (68, 0.150, 264),
        "on-plate": (99, 0.003, 255),
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
    # cuarto de disco en la celda superior derecha
    cx, cy, r = W, 74, 168
    b.append(f'<path d="M{cx} {cy}V{cy + r}A{r} {r} 0 0 1 {cx - r} {cy}Z" fill="{P["signal"]}"/>')
    t, _ = display("santiago", 152, -6, 222, P["ink"])
    b.append(t)
    t, w2 = display("groba alonso", 152, -6, 360, P["ink"])
    b.append(t)
    sq = 0.24 * 152  # cuadrado-punto donde iría el punto final
    b.append(rect(-6 + w2 + 10, 360 - sq, sq, sq, P["signal"]))
    t, _ = text("En producción desde 2020.", 34, 0, 440, P["ink"], 400)
    b.append(t)
    return svg(W, H, "".join(b), "Santiago Groba Alonso — desarrollador de software e IA, en producción desde 2020")


# ---------------------------------------------------------------- figuras de prueba (dípticos)

FW, FH = 600, 420


def frame(P):
    return rails(FW, FH, 6, P["rule"]) + hline(0, FW, 1, P["ink"], 2)


def fig_pdc(P):
    b = [frame(P)]
    t, _ = display("1.182", 124, -4, 132, P["ink"], tnum=True)
    b.append(t)
    t, _ = label("Casas de cambio · 62 ciudades", 19, 0, 170, P["muted"])
    b.append(t)
    cities = [("Bogotá", 226), ("Ipiales", 207), ("Medellín", 150), ("Cartagena", 101), ("Cúcuta", 97)]
    x0, maxw = 200, 300
    for i, (city, n) in enumerate(cities):
        y = 214 + i * 36
        t, _ = text(city, 22, 0, y + 8, P["ink"], 500)
        b.append(t)
        w = maxw * n / cities[0][1]
        b.append(rect(x0, y - 9, w, 18, P["signal"] if i == 0 else P["ink"]))
        t, _ = text(str(n), 22, x0 + w + 12, y + 8, P["muted"], 500, tnum=True)
        b.append(t)
    t, _ = label("Las 5 ciudades con más casas · registro DIAN", 15, 0, 408, P["muted"])
    b.append(t)
    return svg(FW, FH, "".join(b), "PrecioDelDolarCo: 1.182 casas de cambio en 62 ciudades; Bogotá 226, Ipiales 207, Medellín 150, Cartagena 101, Cúcuta 97")


def fig_llm(P):
    b = [frame(P)]
    t, _ = label("Segundos por respuesta", 19, 0, 44, P["muted"])
    b.append(t)
    s = 36  # px por segundo
    for i, (who, sec, num, fill) in enumerate((("antes", 10, "~10 s", P["faint"]), ("ahora", 3, "~3 s", P["signal"]))):
        y = 80 + i * 74
        b.append(rect(0, y, sec * s, 46, fill))
        t, _ = display(num, 46, sec * s + 14, y + 40, P["ink"], tnum=True)
        b.append(t)
        t, _ = label(who, 15, 0, y + 64, P["muted"])
        b.append(t)
    b.append(hline(0, FW, 262, P["hair"]))
    for i, (big, cap) in enumerate((("27B", "Parámetros"), ("FP8", "Precisión"), ("2", "GPU RTX 3090"))):
        x = i * 200
        if i:
            b.append(vline(x, 262, 410, P["hair"]))
        t, _ = display(big, 76, x + (14 if i else 0), 352, P["ink"], tnum=True)
        b.append(t)
        t, _ = label(cap, 15, x + (18 if i else 0), 392, P["muted"])
        b.append(t)
    return svg(FW, FH, "".join(b), "LLM on-premise: de unos 10 a unos 3 segundos por respuesta; 27B parámetros en FP8 sobre dos RTX 3090")


def fig_research(P):
    b = [frame(P)]
    t, _ = label("Qué viaja del turno T1 al T2", 19, 0, 44, P["muted"])
    b.append(t)
    rows = (("preservar", "viaja todo", 270, P["ink"]),
            ("comprimir", "viaja un resumen", 126, P["signal"]),
            ("descartar", "solo la respuesta", 40, P["ink"]))
    for i, (word, note, w, fill) in enumerate(rows):
        y = 116 + i * 104
        t, _ = display(word, 50, -2, y, P["ink"])
        b.append(t)
        t, _ = text(note, 20, 0, y + 32, P["muted"], 400)
        b.append(t)
        b.append(rect(FW - 300, y - 34, w, 34, fill))
    t, _ = label("Esquema · no a escala", 15, 0, 408, P["muted"])
    b.append(t)
    return svg(FW, FH, "".join(b), "CoT-Compress: preservar, comprimir o descartar el razonamiento entre turnos")


def fig_infra(P):
    b = [frame(P)]
    t, _ = label("Desde", 19, 0, 44, P["muted"])
    b.append(t)
    t, _ = display("2020", 76, -2, 116, P["ink"], tnum=True)
    b.append(t)
    cells = (("Soporte remoto", "de equipos"), ("Redes, backups", "y acceso remoto"),
             ("Renovación", "de hardware"), ("Monitoreo con", "Tactical RMM"))
    top = 162
    for i, (l1, l2) in enumerate(cells):
        x, y = (i % 2) * 300, top + (i // 2) * 104
        b.append(hline(x, x + 300, y, P["hair"]))
        if i % 2:
            b.append(vline(x, y, y + 104, P["hair"]))
        pad = 16 if i % 2 else 0
        t, _ = text(l1, 24, x + pad, y + 42, P["ink"], 500)
        b.append(t)
        t, _ = text(l2, 24, x + pad, y + 74, P["ink"], 500)
        b.append(t)
    b.append(rect(0, top - 1.5, 100, 3, P["signal"]))
    return svg(FW, FH, "".join(b), "Infraestructura de escribanías y pymes de CABA desde 2020: soporte, redes, backups, hardware y monitoreo")


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
    builders = {"masthead": masthead, "proof-pdc": fig_pdc, "proof-llm": fig_llm,
                "proof-research": fig_research, "proof-infra": fig_infra,
                "plate": lambda P: plate(P, DATES)}
    for name, fn in builders.items():
        for theme in ("light", "dark"):
            path = out / f"{name}-{theme}.svg"
            path.write_text(fn(palette(theme)), encoding="utf-8")
            print(f"{path.name}: {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    assert len(DATES) == 22
    main(sys.argv[1])
