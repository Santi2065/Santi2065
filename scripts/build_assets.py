#!/usr/bin/env python3
"""Genera los SVG animados del README de perfil de GitHub.

Todo el texto se convierte en trazos (paths) con HarfBuzz + fontTools, así se ve
igual en cualquier sistema sin depender de fuentes instaladas. Las animaciones
que necesitan recorte (clip) usan SMIL; las de giro y parpadeo usan CSS.

Uso: python3 scripts/build_assets.py assets
Requiere: pip install uharfbuzz fonttools brotli; fuentes Inter y JetBrains Mono
(INTER_DIR y MONO_DIR para indicar dónde están).
"""
import io
import math
import os
import random
import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
INTER = Path(os.environ.get("INTER_DIR", "/usr/share/fonts/opentype/inter"))
MONO_DIR = Path(os.environ.get("MONO_DIR", HERE / "npm/node_modules/@fontsource/jetbrains-mono/files"))

# ---------------------------------------------------------------- Colombia (lon, lat)

COLOMBIA = [
    (-77.36, 8.67), (-76.9, 8.6), (-76.3, 9.3), (-75.6, 9.9), (-75.3, 10.5), (-74.8, 11.0),
    (-74.2, 11.3), (-73.5, 11.3), (-72.9, 11.6), (-72.2, 12.0), (-71.7, 12.45), (-71.1, 12.1),
    (-71.4, 11.8), (-72.2, 11.2), (-72.7, 10.6), (-73.0, 9.7), (-73.4, 9.1), (-72.9, 8.6),
    (-72.4, 8.2), (-72.5, 7.6), (-72.0, 7.0), (-71.1, 6.9), (-70.0, 6.9), (-69.3, 6.1),
    (-68.4, 6.2), (-67.5, 6.2), (-67.8, 5.3), (-67.5, 4.2), (-67.3, 3.5), (-67.8, 2.9),
    (-67.3, 2.3), (-67.1, 1.9), (-66.9, 1.2), (-68.2, 0.4), (-69.4, -0.8), (-69.5, -1.2),
    (-69.95, -4.23), (-70.4, -3.8), (-70.9, -2.6), (-71.6, -2.3), (-72.6, -1.8), (-73.6, -1.2),
    (-74.3, -0.6), (-74.8, -0.2), (-75.3, -0.1), (-76.0, 0.3), (-76.9, 0.3), (-77.5, 0.7),
    (-78.2, 1.0), (-78.9, 1.5), (-78.6, 2.2), (-77.9, 2.7), (-77.4, 3.3), (-77.1, 3.9),
    (-77.3, 4.6), (-77.5, 5.4), (-77.4, 6.3), (-77.8, 7.0), (-77.6, 7.6),
]
# ciudades con casas de cambio: (lon, lat, peso)
CIUDADES = [
    (-74.07, 4.71, 3), (-75.56, 6.25, 3), (-76.52, 3.44, 2), (-74.8, 10.96, 2), (-75.5, 10.4, 2),
    (-72.5, 7.89, 3), (-73.12, 7.13, 2), (-75.69, 4.81, 1), (-74.2, 11.24, 1), (-75.23, 4.44, 1),
    (-77.28, 1.21, 1), (-75.52, 5.07, 1), (-73.63, 4.15, 1), (-75.88, 8.75, 1), (-75.28, 2.93, 1),
    (-75.68, 4.53, 1), (-73.25, 10.46, 1), (-76.6, 2.44, 1), (-72.9, 11.54, 1), (-73.36, 5.53, 1),
    (-69.94, -4.21, 1), (-72.4, 5.34, 1), (-77.64, 0.83, 2), (-72.24, 11.38, 2), (-76.65, 5.69, 1),
    (-75.4, 9.3, 1), (-75.6, 1.61, 1),
]


def colombia_projection(box_x, box_y, box_h):
    k = math.cos(math.radians(4.0))
    xs = [lon * k for lon, _ in COLOMBIA]
    ys = [-lat for _, lat in COLOMBIA]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    s = box_h / (maxy - miny)

    def f(lon, lat):
        return box_x + (lon * k - minx) * s, box_y + (-lat - miny) * s

    return f, (maxx - minx) * s


# ---------------------------------------------------------------- tipografía

def ntos(v):
    s = f"{v:.1f}"
    if s.endswith(".0"):
        s = s[:-2]
    return "0" if s == "-0" else s


class Font:
    def __init__(self, path):
        tt = TTFont(str(path))
        tt.flavor = None
        buf = io.BytesIO()
        tt.save(buf)
        data = buf.getvalue()
        self.tt = TTFont(io.BytesIO(data))
        self.upem = self.tt["head"].unitsPerEm
        self.gs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.hb = hb.Font(hb.Face(hb.Blob(data)))

    def shape(self, s):
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True})
        for inf in buf.glyph_infos:
            if inf.codepoint == 0:
                raise ValueError(f"falta un glifo en {s!r}")
        return buf.glyph_infos, buf.glyph_positions

    def width(self, s, size, tracking=0.0):
        infos, pos = self.shape(s)
        return sum(p.x_advance for p in pos) * size / self.upem + tracking * max(len(infos) - 1, 0)

    def d(self, s, size, x, y, anchor="start", tracking=0.0):
        infos, pos = self.shape(s)
        k = size / self.upem
        w = self.width(s, size, tracking)
        if anchor == "middle":
            x -= w / 2
        elif anchor == "end":
            x -= w
        pen = SVGPathPen(self.gs, ntos=ntos)
        cx = x
        for inf, p in zip(infos, pos):
            glyph = self.gs[self.order[inf.codepoint]]
            glyph.draw(TransformPen(pen, (k, 0, 0, -k, cx + p.x_offset * k, y - p.y_offset * k)))
            cx += p.x_advance * k + tracking
        return pen.getCommands(), w


F = {
    "disp": Font(INTER / "InterDisplay-Bold.otf"),
    "dispsemi": Font(INTER / "InterDisplay-SemiBold.otf"),
    "semi": Font(INTER / "Inter-SemiBold.otf"),
    "med": Font(INTER / "Inter-Medium.otf"),
    "reg": Font(INTER / "Inter-Regular.otf"),
    "mono": Font(MONO_DIR / "jetbrains-mono-latin-400-normal.woff2"),
    "monob": Font(MONO_DIR / "jetbrains-mono-latin-700-normal.woff2"),
}


def text(font, s, size, x, y, fill, anchor="start", tracking=0.0, extra=""):
    d, w = F[font].d(s, size, x, y, anchor, tracking)
    ex = f" {extra}" if extra else ""
    return f'<path d="{d}" fill="{fill}"{ex}/>', w


def wrap(font, s, size, maxw):
    lines, cur = [], ""
    for word in s.split():
        t = f"{cur} {word}".strip()
        if F[font].width(t, size) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- estilo

PAL = {
    "dark": dict(bg0="#0a1020", bg1="#111c33", card="#0f1828", cardline="#203049",
                 text="#eaf1fa", text2="#a9b8cc", muted="#73859e", cel="#6cc4ff",
                 gold="#f6c453", green="#3ddc97", red="#ff7b72", grid="#1c2a44", chip="#152238",
                 chipline="#253753", chiptext="#cfe1f5", inner="#0b1322", land="#172641",
                 glowA=0.24, glowB=0.13),
    "light": dict(bg0="#ffffff", bg1="#ebf4fe", card="#ffffff", cardline="#d3e1f1",
                  text="#0d1a2c", text2="#3b4b61", muted="#687a92", cel="#1a72d6",
                  gold="#b8790c", green="#14965a", red="#d1242f", grid="#dce7f4", chip="#edf4fc",
                  chipline="#d0dff1", chiptext="#1b3a5e", inner="#f3f8fd", land="#dbe8f7",
                  glowA=0.20, glowB=0.18),
}

CSS = """<style>
.pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2.2s ease-out infinite}
@keyframes pulse{0%{transform:scale(1);opacity:.7}100%{transform:scale(3.4);opacity:0}}
.spin{transform-box:fill-box;transform-origin:center;animation:spin 1s linear infinite}
.spin-slow{transform-box:fill-box;transform-origin:center;animation:spin 5s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.blink{animation:blink 1.1s steps(1) infinite}
@keyframes blink{50%{opacity:0}}
.led{animation:led 1.6s ease-in-out infinite}
@keyframes led{50%{opacity:.2}}
.bob{animation:bob 1.2s ease-in-out infinite}
@keyframes bob{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-5px)}}
.flow{animation:flow 3s linear infinite}
@keyframes flow{from{transform:translateX(0)}to{transform:translateX(-60px)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
</style>"""


def svg(w, h, body, label, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{label}">'
            f"<title>{label}</title><defs>{defs}</defs>{CSS}{body}</svg>\n")


def card_frame(w, h, P, accent, uid, gx=0.95, gy=0.05):
    defs = (f'<radialGradient id="{uid}g" cx="{gx}" cy="{gy}" r="0.85">'
            f'<stop offset="0" stop-color="{accent}" stop-opacity="{P["glowA"]}"/>'
            f'<stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>'
            f'<clipPath id="{uid}clip"><rect width="{w}" height="{h}" rx="18"/></clipPath>')
    body = (f'<rect x="0.75" y="0.75" width="{w - 1.5}" height="{h - 1.5}" rx="18" '
            f'fill="{P["card"]}" stroke="{P["cardline"]}" stroke-width="1.5"/>'
            f'<g clip-path="url(#{uid}clip)"><rect width="{w}" height="{h}" fill="url(#{uid}g)"/></g>')
    return defs, body


def badge(xr, y, label, color, P, pulse=False):
    size, h, pad = 15, 30, 12
    tw = F["med"].width(label, size)
    w = pad + 9 + 8 + tw + pad
    x = xr - w
    cx, cy = x + pad + 4.5, y + h / 2
    out = [f'<rect x="{ntos(x)}" y="{y}" width="{ntos(w)}" height="{h}" rx="{h / 2}" '
           f'fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-opacity="0.45"/>']
    if pulse:
        out.append(f'<circle class="pulse" cx="{ntos(cx)}" cy="{ntos(cy)}" r="4.5" fill="{color}"/>')
    out.append(f'<circle cx="{ntos(cx)}" cy="{ntos(cy)}" r="4.5" fill="{color}"/>')
    t, _ = text("med", label, size, x + pad + 17, cy + size * 0.36, color)
    out.append(t)
    return "".join(out)


def chip(x, y, label, P, size=15, h=28, pad=11, font="mono", fill=None, line=None, color=None):
    w = F[font].width(label, size) + 2 * pad
    t, _ = text(font, label, size, x + pad, y + h / 2 + size * 0.36, color or P["chiptext"])
    return (f'<rect x="{ntos(x)}" y="{ntos(y)}" width="{ntos(w)}" height="{h}" rx="{h / 2}" '
            f'fill="{fill or P["chip"]}" stroke="{line or P["chipline"]}"/>' + t), w


def chips(x, y, labels, P, size=15, h=28, gap=8, maxx=None):
    out, cx = [], x
    for lab in labels:
        s, w = chip(cx, y, lab, P, size, h)
        if maxx is not None and cx + w > maxx:
            break
        out.append(s)
        cx += w + gap
    return "".join(out), cx - gap


def mono_label(s, size, x, y, P, color=None, anchor="start"):
    t, w = text("mono", s, size, x, y, color or P["muted"], anchor=anchor)
    return t, w


# ---------------------------------------------------------------- íconos y piezas

def icon_db(cx, cy, c):
    return (f'<g fill="none" stroke="{c}" stroke-width="2" stroke-linecap="round">'
            f'<ellipse cx="{cx}" cy="{cy - 9}" rx="11" ry="4"/>'
            f'<path d="M{cx - 11} {cy - 9}v18a11 4 0 0 0 22 0v-18"/>'
            f'<path d="M{cx - 11} {cy}a11 4 0 0 0 22 0"/></g>')


def icon_net(cx, cy, c):
    pts = [(cx - 10, cy - 9), (cx - 10, cy + 9), (cx + 11, cy)]
    lines = "".join(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}"/>'
                    for i, a in enumerate(pts) for b in pts[i + 1:])
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="3.6" fill="{c}"/>' for x, y in pts)
    return f'<g stroke="{c}" stroke-width="1.6" stroke-opacity="0.7">{lines}</g>{dots}'


def icon_server(cx, cy, c, led):
    return (f'<g fill="none" stroke="{c}" stroke-width="2"><rect x="{cx - 12}" y="{cy - 12}" '
            f'width="24" height="24" rx="4"/><line x1="{cx - 12}" y1="{cy}" x2="{cx + 12}" y2="{cy}"/></g>'
            f'<circle class="led" cx="{cx + 6}" cy="{cy - 6}" r="2" fill="{led}"/>'
            f'<circle class="led" style="animation-delay:.8s" cx="{cx + 6}" cy="{cy + 6}" r="2" fill="{led}"/>')


def icon_lock(cx, cy, c, k=1.0):
    return (f'<g transform="translate({ntos(cx)} {ntos(cy)}) scale({k})" fill="none" stroke="{c}" '
            f'stroke-width="1.8" stroke-linecap="round">'
            f'<rect x="-6" y="-2" width="12" height="10" rx="2.2"/>'
            f'<path d="M-3.6 -2v-3a3.6 3.6 0 0 1 7.2 0v3"/></g>')


def icon_check(cx, cy, c):
    return (f'<circle cx="{cx}" cy="{cy}" r="8" fill="{c}" fill-opacity="0.15"/>'
            f'<path d="M{cx - 3.6} {cy}l2.4 2.6l4.8-5.2" fill="none" stroke="{c}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')


def icon_docs(cx, cy, c, c2):
    """Pila de dos documentos."""
    out = []
    for dx, dy in ((5, -5), (0, 0)):
        x, y = cx - 11 + dx, cy - 14 + dy
        out.append(f'<path d="M{x} {y}h14l8 8v20h-22z" fill="{c2}" stroke="{c}" stroke-width="1.6" '
                   f'stroke-linejoin="round"/>')
        if dy == 0:
            for k in range(3):
                out.append(f'<line x1="{x + 4}" y1="{y + 12 + k * 5}" x2="{x + 17}" y2="{y + 12 + k * 5}" '
                           f'stroke="{c}" stroke-width="1.4" stroke-linecap="round" stroke-opacity="0.7"/>')
    return "".join(out)


def icon_chat(cx, cy, c, c2):
    return (f'<path d="M{cx - 14} {cy - 10}h28a4 4 0 0 1 4 4v12a4 4 0 0 1 -4 4h-14l-8 7v-7h-6a4 4 0 0 1 -4 -4v-12'
            f'a4 4 0 0 1 4 -4z" fill="{c2}" stroke="{c}" stroke-width="1.6" stroke-linejoin="round"/>'
            f'<circle cx="{cx - 6}" cy="{cy}" r="1.8" fill="{c}"/><circle cx="{cx}" cy="{cy}" r="1.8" fill="{c}"/>'
            f'<circle cx="{cx + 6}" cy="{cy}" r="1.8" fill="{c}"/>')


def icon_refresh(cx, cy, r, c):
    a0, a1 = math.radians(-60), math.radians(240)
    x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
    x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
    tip = f'M{ntos(x0 - 5)} {ntos(y0 - 1)}L{ntos(x0 + 1)} {ntos(y0 + 1)}L{ntos(x0 - 1)} {ntos(y0 - 6)}'
    return (f'<g class="spin-slow"><circle cx="{cx}" cy="{cy}" r="{r + 3}" fill="none"/>'
            f'<path d="M{ntos(x1)} {ntos(y1)}A{r} {r} 0 1 1 {ntos(x0)} {ntos(y0)}" fill="none" '
            f'stroke="{c}" stroke-width="2.4" stroke-linecap="round"/>'
            f'<path d="{tip}" fill="none" stroke="{c}" stroke-width="2.4" stroke-linecap="round" '
            f'stroke-linejoin="round"/></g>')


def arrow_down(x, y1, y2, c):
    return (f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2 - 2}" stroke="{c}" stroke-width="2"/>'
            f'<path d="M{x - 5} {y2 - 7}L{x} {y2}L{x + 5} {y2 - 7}" fill="none" stroke="{c}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')


def arrow_right(x1, x2, y, c):
    return (f'<line x1="{x1}" y1="{y}" x2="{x2 - 2}" y2="{y}" stroke="{c}" stroke-width="2"/>'
            f'<path d="M{x2 - 7} {y - 5}L{x2} {y}L{x2 - 7} {y + 5}" fill="none" stroke="{c}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')


def packet(path, c, dur, begin, r=4):
    """Punto que recorre un camino, repitiendo."""
    return (f'<circle r="{r}" fill="{c}" opacity="0">'
            f'<animateMotion path="{path}" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.15;0.8;1" '
            f'dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/></circle>')


def packet_window(path, c, cycle, t0, t1, r=4):
    """Punto que recorre un camino solo entre t0 y t1 (fracciones) de un ciclo."""
    e = 0.004
    return (f'<circle r="{r}" fill="{c}" opacity="0">'
            f'<animateMotion path="{path}" dur="{cycle}s" keyPoints="0;0;1;1" '
            f'keyTimes="0;{t0};{t1};1" calcMode="linear" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;0;1;1;0;0" '
            f'keyTimes="0;{t0};{t0 + e};{t1 - e};{t1};1" dur="{cycle}s" repeatCount="indefinite"/></circle>')


def show_window(inner, cycle, t0, t1):
    """Muestra un grupo solo entre t0 y t1 (fracciones) de un ciclo."""
    e = 0.004
    return (f'<g opacity="0">{inner}<animate attributeName="opacity" values="0;0;1;1;0;0" '
            f'keyTimes="0;{t0};{t0 + e};{t1 - e};{t1};1" dur="{cycle}s" repeatCount="indefinite"/></g>')


# ---------------------------------------------------------------- banner

PHRASES = [
    "despliego LLMs on-premise",
    "llevo modelos a producción",
    "armo pipelines de datos",
    "investigo razonamiento en LLMs",
    "estudio Ingeniería en IA @ UdeSA",
]


def typewriter(phrases, x0, y, size, P, prefix="tw"):
    mono = F["mono"]
    cw = mono.width("M", size)
    tau = 0.055
    defs, body, cursor_anims = [], [], []
    n = len(phrases)
    for i, ph in enumerate(phrases):
        d, _ = mono.d(ph, size, x0, y)
        L = len(ph)
        steps = ([k * cw for k in range(L + 1)] + [L * cw] * 36
                 + [max(L - 3 * k, 0) * cw for k in range(1, math.ceil(L / 3) + 1)] + [0] * 6)
        dur = len(steps) * tau
        vals = ";".join(ntos(v) for v in steps)
        cvals = ";".join(ntos(x0 + v) for v in steps)
        begin = f"0s;{prefix}{n - 1}.end" if i == 0 else f"{prefix}{i - 1}.end"
        init = L * cw if i == 0 else 0
        defs.append(f'<clipPath id="{prefix}c{i}"><rect x="{ntos(x0)}" y="{ntos(y - size * 1.05)}" '
                    f'width="{ntos(init)}" height="{ntos(size * 1.5)}">'
                    f'<animate id="{prefix}{i}" attributeName="width" values="{vals}" dur="{dur:.2f}s" '
                    f'begin="{begin}" calcMode="discrete" fill="freeze"/></rect></clipPath>')
        body.append(f'<path d="{d}" fill="{P["text"]}" clip-path="url(#{prefix}c{i})"/>')
        cursor_anims.append(f'<animate attributeName="x" values="{cvals}" dur="{dur:.2f}s" '
                            f'begin="{begin}" calcMode="discrete" fill="freeze"/>')
    first = len(phrases[0]) * cw
    body.append(f'<rect class="blink" x="{ntos(x0 + first + 2)}" y="{ntos(y - size * 0.86)}" '
                f'width="{ntos(cw * 0.62)}" height="{ntos(size * 1.08)}" rx="1.5" fill="{P["cel"]}">'
                + "".join(cursor_anims) + "</rect>")
    return "".join(defs), "".join(body)


def banner(P):
    W, H = 1200, 320
    defs = [
        f'<linearGradient id="bbg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{P["bg0"]}"/>'
        f'<stop offset="1" stop-color="{P["bg1"]}"/></linearGradient>',
        f'<radialGradient id="bgA"><stop offset="0" stop-color="{P["cel"]}" stop-opacity="{P["glowA"]}"/>'
        f'<stop offset="1" stop-color="{P["cel"]}" stop-opacity="0"/></radialGradient>',
        f'<radialGradient id="bgB"><stop offset="0" stop-color="{P["gold"]}" stop-opacity="{P["glowB"]}"/>'
        f'<stop offset="1" stop-color="{P["gold"]}" stop-opacity="0"/></radialGradient>',
        '<linearGradient id="bfade" gradientUnits="userSpaceOnUse" x1="560" y1="0" x2="920" y2="0">'
        '<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity="1"/>'
        '</linearGradient>',
        f'<mask id="bmask"><rect width="{W}" height="{H}" fill="url(#bfade)"/></mask>',
        f'<clipPath id="bclip"><rect width="{W}" height="{H}" rx="20"/></clipPath>',
    ]
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="1.4" fill="{P["grid"]}"/>'
                   for x in range(560, W, 22) for y in range(18, H, 22))
    body = [
        f'<rect width="{W}" height="{H}" rx="20" fill="url(#bbg)"/>',
        f'<g clip-path="url(#bclip)"><circle cx="230" cy="70" r="430" fill="url(#bgA)"/>'
        f'<circle cx="1110" cy="330" r="360" fill="url(#bgB)"/><g mask="url(#bmask)">{dots}</g></g>',
    ]
    t, _ = text("mono", "// hola, soy", 19, 66, 92, P["muted"])
    body.append(t)
    t, wname = text("disp", "Santiago Groba Alonso", 64, 62, 160, P["text"])
    body.append(t)
    t, _ = text("med", "Desarrollador de Software e Inteligencia Artificial", 27, 66, 205, P["text2"])
    body.append(t)
    t, _ = text("monob", "$", 21, 66, 256, P["gold"])
    body.append(t)
    x0 = 66 + F["mono"].width("$ ", 21)
    tdefs, tbody = typewriter(PHRASES, x0, 256, 21, P)
    defs.append(tdefs)
    body.append(tbody)

    # circuito vertical: datos -> modelos -> producción, con paquetes bajando
    bx, bw, bh = 914, 240, 58
    ys = [36, 131, 226]
    labels = ["datos", "modelos", "producción"]
    for i, (y, lab) in enumerate(zip(ys, labels)):
        last = i == 2
        stroke = P["gold"] if last else P["cardline"]
        body.append(f'<rect x="{bx}" y="{y}" width="{bw}" height="{bh}" rx="14" fill="{P["card"]}" '
                    f'fill-opacity="0.9" stroke="{stroke}" stroke-width="{2 if last else 1.5}"/>')
        cy = y + bh / 2
        if i == 0:
            body.append(icon_db(bx + 34, cy, P["cel"]))
        elif i == 1:
            body.append(icon_net(bx + 34, cy, P["cel"]))
        else:
            body.append(icon_server(bx + 34, cy, P["gold"], P["green"]))
        t, _ = text("mono", lab, 20, bx + 66, cy + 7, P["text"])
        body.append(t)
        if last:
            sx = bx + bw - 26
            body.append(f'<circle class="pulse" cx="{sx}" cy="{cy}" r="5" fill="{P["green"]}"/>'
                        f'<circle cx="{sx}" cy="{cy}" r="5" fill="{P["green"]}"/>')
        if i < 2:
            ax = bx + bw / 2
            y1, y2 = y + bh + 5, ys[i + 1] - 5
            body.append(arrow_down(ax, y1, y2, P["cel"]))
            for k in range(2):
                body.append(packet(f"M{ax} {y1 + 2} L{ax} {y2 - 8}", P["cel"], 1.6, k * 0.8 + i * 0.4, r=4.2))
    label = "Santiago Groba Alonso — Desarrollador de Software e Inteligencia Artificial"
    assert wname < bx - 100, wname
    return svg(W, H, "".join(body), label, "".join(defs))


# ---------------------------------------------------------------- tarjetas de trabajo

CW, CH = 560, 290


def card_head(P, title, subtitle):
    out = []
    t, _ = text("semi", title, 28, 30, 58, P["text"])
    out.append(t)
    t, _ = text("reg", subtitle, 16.5, 30, 90, P["text2"])
    out.append(t)
    return "".join(out)


def stat(x, y, big, label, P, unit=None, size=46):
    out = []
    t, wb = text("disp", big, size, x, y, P["text"])
    out.append(t)
    wu = 0
    if unit:
        t, wu = text("dispsemi", unit, size * 0.55, x + wb + 6, y, P["text2"])
        out.append(t)
        wu += 6
    t, wl = text("reg", label, 15, x + 2, y + 24, P["muted"])
    out.append(t)
    return "".join(out), max(wb + wu, wl), wb + wu


def card_pdc(P):
    """PrecioDelDolarCo: el scraper barre el mapa de Colombia cada 30 minutos."""
    defs, frame = card_frame(CW, CH, P, P["gold"], "p")
    out = [frame, card_head(P, "PrecioDelDolarCo", "Comparador de tasas de cambio en Colombia")]
    out.append(badge(530, 33, "en producción", P["green"], P, pulse=True))

    s1, _, _ = stat(30, 142, "1.182", "casas de cambio en 62 ciudades", P, size=46)
    out.append(s1)
    for k, item in enumerate(["Scraper con 80 fuentes y 13 parsers", "Panel para dueños con planes pagos"]):
        y = 195 + k * 25
        out.append(icon_check(38, y - 5, P["gold"]))
        t, _ = text("reg", item, 15.5, 56, y, P["text2"])
        out.append(t)

    # mapa de Colombia con las ciudades donde hay casas de cambio
    mx, my, mh = 410, 66, 142
    proj, mw = colombia_projection(mx, my, mh)
    pts = " ".join(f"{ntos(x)},{ntos(y)}" for x, y in (proj(lo, la) for lo, la in COLOMBIA))
    defs += (f'<clipPath id="pmap"><polygon points="{pts}"/></clipPath>'
             f'<linearGradient id="ptrail" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0" stop-color="{P["gold"]}" stop-opacity="0"/>'
             f'<stop offset="1" stop-color="{P["gold"]}" stop-opacity="0.28"/></linearGradient>')
    out.append(f'<polygon points="{pts}" fill="{P["land"]}" stroke="{P["cel"]}" stroke-opacity="0.75" '
               f'stroke-width="1.3" stroke-linejoin="round"/>')
    cycle = 3.2
    for lo, la, wt in CIUDADES:
        x, y = proj(lo, la)
        r = 1.8 + wt * 0.9
        out.append(f'<circle cx="{ntos(x)}" cy="{ntos(y)}" r="{ntos(r)}" fill="{P["muted"]}" fill-opacity="0.55"/>')
        delay = (y - my) / mh * cycle
        out.append(f'<circle cx="{ntos(x)}" cy="{ntos(y)}" r="{ntos(r + 1.2)}" fill="{P["gold"]}" opacity="0">'
                   f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.02;0.18;0.5;1" '
                   f'dur="{cycle}s" begin="{delay:.2f}s" repeatCount="indefinite"/></circle>')
    # barrido de norte a sur, recortado por el mapa (SMIL, para que el recorte funcione)
    out.append(f'<g clip-path="url(#pmap)"><g>'
               f'<rect x="{mx - 2}" y="-34" width="{ntos(mw + 4)}" height="34" fill="url(#ptrail)"/>'
               f'<line x1="{mx - 2}" y1="0" x2="{ntos(mx + mw + 2)}" y2="0" stroke="{P["gold"]}" stroke-width="2"/>'
               f'<animateTransform attributeName="transform" type="translate" values="0 {my};0 {my + mh + 2}" '
               f'dur="{cycle}s" repeatCount="indefinite"/></g></g>')
    cap, _ = mono_label("~1.120 puntos en el mapa", 12.5, mx + mw / 2, my + mh + 20, P, anchor="middle")
    out.append(cap)

    link, wl = text("med", "preciodeldolar.com.co ↗", 15, 530, 257, P["cel"], anchor="end")
    c, _ = chips(30, 238, ["Next.js", "PostgreSQL", "Puppeteer"], P, maxx=530 - wl - 16)
    out += [c, link]
    return svg(CW, CH, "".join(out), "PrecioDelDolarCo: comparador de tasas de cambio en producción", defs)


def blades(r, color, n=7):
    out = [f'<circle r="{r}" fill="none"/>']
    for k in range(n):
        a = 360 * k / n
        out.append(f'<path transform="rotate({a:.1f})" d="M0 0C{ntos(r * .15)} {ntos(-r * .55)} '
                   f'{ntos(r * .62)} {ntos(-r * .8)} {ntos(r * .92)} {ntos(-r * .34)}'
                   f'C{ntos(r * .55)} {ntos(-r * .26)} {ntos(r * .25)} {ntos(-r * .06)} 0 0Z" '
                   f'fill="{color}" fill-opacity="0.85"/>')
    return "".join(out)


def gpu(x, y, w, h, P, durs, label=None):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{P["inner"]}" '
           f'stroke="{P["cardline"]}" stroke-width="1.5"/>']
    for i, fx in enumerate([x + w * 0.3, x + w * 0.7]):
        fy, r = y + h / 2, h * 0.34
        out.append(f'<circle cx="{ntos(fx)}" cy="{ntos(fy)}" r="{ntos(r + 2)}" fill="none" '
                   f'stroke="{P["cardline"]}" stroke-width="1.5"/>')
        out.append(f'<g transform="translate({ntos(fx)} {ntos(fy)})"><g class="spin" '
                   f'style="animation-duration:{durs[i]}s">{blades(r, P["cel"])}</g></g>')
        out.append(f'<circle cx="{ntos(fx)}" cy="{ntos(fy)}" r="{ntos(r * 0.24)}" fill="{P["muted"]}"/>')
    if label:
        t, _ = mono_label(label, 10.5, x + w - 8, y + h / 2 + 4, P, anchor="end")
        out.append(t)
    return "".join(out)


def card_llm(P):
    """LLM on-premise: documentos y consultas se procesan adentro de la oficina."""
    defs, frame = card_frame(CW, CH, P, P["cel"], "l")
    out = [frame, card_head(P, "LLM on-premise", "Para el archivo de escrituras de una escribanía")]
    out.append(badge(530, 33, "en producción", P["green"], P, pulse=True))
    s1, _, _ = stat(30, 140, "27B", "parámetros · Qwen3.8 en FP8", P, size=42)
    out.append(s1)
    s2, _, _ = stat(30, 202, "~3", "por respuesta (antes ~10 s)", P, unit="s", size=42)
    out.append(s2)

    # límite de la oficina: línea punteada con candado
    bx, by, bw, bh = 316, 102, 222, 124
    out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="14" fill="{P["inner"]}" fill-opacity="0.5" '
               f'stroke="{P["cel"]}" stroke-opacity="0.6" stroke-width="1.5" stroke-dasharray="5 5"/>')
    lab, lw = mono_label("oficina", 12.5, bx + 34, by + 4.5, P, color=P["cel"])
    out.append(f'<rect x="{bx + 12}" y="{by - 9}" width="{ntos(lw + 32)}" height="18" rx="9" fill="{P["card"]}"/>')
    out.append(icon_lock(bx + 24, by, P["cel"], k=0.85))
    out.append(lab)

    # adentro: documentos y consultas entran al servidor con las dos GPUs; nada sale
    gx, gy, gw, gh = 430, 116, 96, 42
    out.append(gpu(gx, gy, gw, gh, P, (0.9, 1.15)))
    out.append(gpu(gx, gy + 52, gw, gh, P, (1.05, 0.8)))
    out.append(icon_docs(352, 136, P["text2"], P["card"]))
    out.append(icon_chat(352, 186, P["text2"], P["card"]))
    p1 = f"M378 136 C400 136 404 {gy + gh / 2} 424 {gy + gh / 2}"
    p2 = f"M378 186 C400 186 404 {gy + 52 + gh / 2} 424 {gy + 52 + gh / 2}"
    p2r = f"M424 {gy + 52 + gh / 2} C404 {gy + 52 + gh / 2} 400 186 378 186"
    out.append(f'<path d="{p1}" fill="none" stroke="{P["cardline"]}" stroke-width="1.6"/>'
               f'<path d="{p2}" fill="none" stroke="{P["cardline"]}" stroke-width="1.6"/>')
    for k in range(2):
        out.append(packet(p1, P["gold"], 2.2, k * 1.1, r=3.4))          # ingesta de escrituras
    out.append(packet_window(p2, P["cel"], 3.0, 0.05, 0.4, r=3.4))     # pregunta
    out.append(packet_window(p2r, P["green"], 3.0, 0.55, 0.9, r=3.4))  # respuesta
    cap1, _ = mono_label("escrituras", 11, 352, 166, P, anchor="middle")
    cap2, _ = mono_label("consultas", 11, 352, 214, P, anchor="middle")
    out += [cap1, cap2]

    c, _ = chips(30, 238, ["vLLM", "Qdrant", "PostgreSQL", "RAG"], P, maxx=530)
    out.append(c)
    return svg(CW, CH, "".join(out), "LLM on-premise: Qwen 3.6 27B en dos RTX 3090, dentro de la oficina", defs)


def card_research(P):
    """Investigación: qué parte del razonamiento de T1 viaja a T2 y qué cuesta."""
    defs, frame = card_frame(CW, CH, P, P["cel"], "r")
    out = [frame, card_head(P, "Investigación", "¿Preservar o descartar el razonamiento de un LLM entre turnos?")]
    out.append(badge(530, 33, "paper en preparación", P["cel"], P))
    defs += (f'<pattern id="rstr" width="9" height="9" patternUnits="userSpaceOnUse" '
             f'patternTransform="rotate(45)"><rect width="9" height="9" fill="{P["cel"]}" fill-opacity="0.22"/>'
             f'<rect width="3.5" height="9" fill="{P["cel"]}" fill-opacity="0.75"/></pattern>')

    def bubble(x, label):
        t, _ = text("monob", label, 17, x + 28, 155, P["text"], anchor="middle")
        return (f'<rect x="{x}" y="127" width="56" height="42" rx="12" fill="{P["chip"]}" '
                f'stroke="{P["chipline"]}" stroke-width="1.5"/>' + t)

    cap, _ = mono_label("razonamiento de T1 que viaja a T2", 12.5, 102, 118, P)
    out.append(cap)
    out.append(bubble(30, "T1"))
    tx, tw, ty, th = 102, 330, 138, 20
    cycle = 7.5
    out.append(f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="10" fill="{P["inner"]}" '
               f'stroke="{P["cardline"]}" stroke-dasharray="4 4"/>')
    out.append(f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="10" fill="url(#rstr)">'
               f'<animate attributeName="width" values="{tw};{tw};128;128;14;14;{tw}" '
               f'keyTimes="0;0.30;0.36;0.62;0.68;0.93;1" dur="{cycle}s" repeatCount="indefinite"/></rect>')
    out.append(arrow_right(tx + tw + 8, 470, ty + th / 2, P["muted"]))
    out.append(bubble(474, "T2"))
    # tokens de entrada por episodio, medidos en Terminal-Bench 2.0 (pruebas exploratorias propias):
    # preservar 83.463 · comprimir (structured) 41.954 · descartar 91.211 -> descartar NO sale más barato
    tk, _ = mono_label("tokens de entrada", 12.5, 102, 211, P)
    out.append(tk)
    kx, kw = 248, 150
    tok = {"preservar": 83463, "comprimir": 41954, "descartar": 91211}
    wmax = max(tok.values())
    wp, wc, wd = (ntos(kw * tok[k] / wmax) for k in ("preservar", "comprimir", "descartar"))
    out.append(f'<rect x="{kx}" y="201" width="{kw}" height="10" rx="5" fill="{P["inner"]}" stroke="{P["cardline"]}"/>')
    out.append(f'<rect x="{kx}" y="201" width="{wp}" height="10" rx="5" fill="{P["gold"]}" fill-opacity="0.85">'
               f'<animate attributeName="width" values="{wp};{wp};{wc};{wc};{wd};{wd};{wp}" '
               f'keyTimes="0;0.30;0.36;0.62;0.68;0.93;1" dur="{cycle}s" repeatCount="indefinite"/></rect>')
    states = [("preservar · viaja todo", "83k", "0;0.30;0.33;0.95;0.98;1", "1;1;0;0;1;1"),
              ("comprimir · viaja un resumen", "42k", "0;0.33;0.36;0.62;0.65;1", "0;0;1;1;0;0"),
              ("descartar · solo la respuesta", "91k", "0;0.65;0.68;0.93;0.96;1", "0;0;1;1;0;0")]
    for i, (lab, num, kt, vals) in enumerate(states):
        anim = (f'<animate attributeName="opacity" values="{vals}" keyTimes="{kt}" dur="{cycle}s" '
                f'repeatCount="indefinite"/>')
        d, _ = F["mono"].d(lab, 14.5, 102, 189)
        out.append(f'<path d="{d}" fill="{P["text2"]}" opacity="{1 if i == 0 else 0}">{anim}</path>')
        d, _ = F["monob"].d(num, 13, kx + kw + 10, 211)
        out.append(f'<path d="{d}" fill="{P["gold"]}" opacity="{1 if i == 0 else 0}">{anim}</path>')
    src, _ = mono_label("Terminal-Bench 2.0 · pruebas exploratorias propias", 11, 102, 230, P)
    out.append(src)
    link, wl = text("med", "CoT-Compress ↗", 15, 530, 257, P["cel"], anchor="end")
    t, _ = mono_label("dirigido por Juan Wisznia (UdeSA)", 14, 30, 257, P)
    out += [t, link]
    return svg(CW, CH, "".join(out), "Investigación: razonamiento de LLMs entre turnos, paper en preparación", defs)


def pc_icon(cx, cy, P):
    return (f'<rect x="{ntos(cx - 13)}" y="{ntos(cy - 10)}" width="26" height="17" rx="3" fill="{P["inner"]}" '
            f'stroke="{P["text2"]}" stroke-width="1.6"/>'
            f'<line x1="{ntos(cx)}" y1="{ntos(cy + 7)}" x2="{ntos(cx)}" y2="{ntos(cy + 11)}" '
            f'stroke="{P["text2"]}" stroke-width="1.6"/>'
            f'<line x1="{ntos(cx - 6)}" y1="{ntos(cy + 11.5)}" x2="{ntos(cx + 6)}" y2="{ntos(cy + 11.5)}" '
            f'stroke="{P["text2"]}" stroke-width="1.6" stroke-linecap="round"/>')


def card_infra(P):
    """Infraestructura: los equipos reportan al RMM; una alerta se detecta y se resuelve."""
    defs, frame = card_frame(CW, CH, P, P["green"], "i")
    out = [frame, card_head(P, "Infraestructura", "Escribanías y pymes de CABA")]
    out.append(badge(530, 33, "desde 2020", P["text2"], P))
    items = ["Soporte remoto de equipos", "Redes, backups y acceso remoto", "Renovación de hardware"]
    for k, it in enumerate(items):
        y = 132 + k * 32
        out.append(icon_check(38, y - 5, P["green"]))
        t, _ = text("reg", it, 16, 56, y, P["text2"])
        out.append(t)

    sx, sy = 492, 160
    pcs = [(372, 108 + k * 34) for k in range(4)]
    paths_in, paths_out = [], []
    for px, py in pcs:
        a, b = f"{px + 15} {py}", f"{sx - 17} {sy}"
        c1, c2 = f"{px + 50} {py}", f"{sx - 60} {sy}"
        paths_in.append(f"M{a} C{c1} {c2} {b}")
        paths_out.append(f"M{b} C{c2} {c1} {a}")
        out.append(f'<path d="M{a} C{c1} {c2} {b}" fill="none" stroke="{P["cardline"]}" stroke-width="1.6"/>')
    cycle = 6.0
    # latidos: cada equipo reporta al servidor
    for k, p in enumerate(paths_in):
        out.append(packet(p, P["green"], 2.4, k * 0.6, r=2.6))
    # historia: el equipo 2 avisa un problema, el servidor responde, queda resuelto
    ax, ay = pcs[1]
    alert = (f'<circle cx="{ax + 14}" cy="{ay - 12}" r="7.5" fill="{P["gold"]}"/>'
             f'<rect x="{ax + 13.1}" y="{ay - 16.5}" width="1.8" height="5.6" rx="0.9" fill="{P["card"]}"/>'
             f'<circle cx="{ax + 14}" cy="{ay - 8.6}" r="1.1" fill="{P["card"]}"/>')
    out.append(show_window(alert, cycle, 0.14, 0.58))
    out.append(packet_window(paths_in[1], P["gold"], cycle, 0.2, 0.33, r=4))
    flash = f'<rect x="{sx - 17}" y="{sy - 26}" width="34" height="52" rx="6" fill="{P["gold"]}" fill-opacity="0.25"/>'
    out.append(show_window(flash, cycle, 0.33, 0.45))
    out.append(packet_window(paths_out[1], P["green"], cycle, 0.45, 0.58, r=4))
    ok = (f'<circle cx="{ax + 14}" cy="{ay - 12}" r="7.5" fill="{P["green"]}"/>'
          f'<path d="M{ax + 10.4} {ay - 12}l2.4 2.6l4.8-5.2" fill="none" stroke="{P["card"]}" stroke-width="2" '
          f'stroke-linecap="round" stroke-linejoin="round"/>')
    out.append(show_window(ok, cycle, 0.58, 0.92))
    for px, py in pcs:
        out.append(pc_icon(px, py, P))
    out.append(f'<rect x="{sx - 17}" y="{sy - 26}" width="34" height="52" rx="6" fill="{P["inner"]}" '
               f'stroke="{P["gold"]}" stroke-width="2"/>')
    for k in range(3):
        y = sy - 16 + k * 14
        out.append(f'<line x1="{sx - 10}" y1="{y}" x2="{sx + 4}" y2="{y}" stroke="{P["text2"]}" '
                   f'stroke-width="1.8" stroke-linecap="round"/>'
                   f'<circle class="led" style="animation-delay:{k * 0.4:.1f}s" cx="{sx + 9}" cy="{y}" r="2.2" '
                   f'fill="{P["green"]}"/>')
    cap, _ = mono_label("RMM", 11, sx, sy + 40, P, anchor="middle")
    out.append(cap)
    c, _ = chips(30, 238, ["Tactical RMM", "Windows", "Linux", "PowerShell"], P, maxx=530)
    out.append(c)
    return svg(CW, CH, "".join(out), "Infraestructura de escribanías y estudios desde 2020", defs)


# ---------------------------------------------------------------- tarjetas de la facultad

UW, UH = 560, 210


def uni_frame(P, accent, uid, title, tag, desc):
    defs, frame = card_frame(UW, UH, P, accent, uid, gx=0.95, gy=0.0)
    out = [frame]
    t, _ = text("semi", title, 24, 28, 50, P["text"])
    out.append(t)
    tagw = F["mono"].width(tag, 14) + 22
    s, _ = chip(532 - tagw, 30, tag, P, size=14, h=26)
    out.append(s)
    for k, line in enumerate(wrap("reg", desc, 16, 300)):
        t, _ = text("reg", line, 16, 28, 84 + k * 22, P["text2"])
        out.append(t)
    return defs, out


def uni_cot(P):
    """CoT-Compress: el razonamiento del turno anterior vuelve comprimido como memoria."""
    defs, out = uni_frame(P, P["cel"], "uc", "CoT-Compress", "NLP · 2026",
                          "Chat local que comprime el razonamiento del modelo y lo reinyecta como memoria.")
    t, wb = text("disp", "6", 38, 28, 176, P["text"])
    t2, _ = text("reg", "estrategias de compresión", 15, 28 + wb + 10, 176, P["muted"])
    out += [t, t2]
    defs += (f'<pattern id="ucstr" width="8" height="8" patternUnits="userSpaceOnUse" '
             f'patternTransform="rotate(45)"><rect width="8" height="8" fill="{P["cel"]}" fill-opacity="0.16"/>'
             f'<rect width="3" height="8" fill="{P["cel"]}" fill-opacity="0.6"/></pattern>')

    def user_bubble(x, y, w):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="26" rx="13" fill="{P["chip"]}" stroke="{P["chipline"]}"/>'
                f'<line x1="{x + 14}" y1="{y + 13}" x2="{x + w - 14}" y2="{y + 13}" stroke="{P["text2"]}" '
                f'stroke-width="3" stroke-linecap="round" stroke-opacity="0.5"/>')

    # turno 1: el usuario pregunta y el modelo razona (burbuja rayada, larga)
    out.append(user_bubble(430, 62, 100))
    out.append(f'<rect x="352" y="98" width="150" height="30" rx="15" fill="{P["cel"]}" fill-opacity="0.14" '
               f'stroke="{P["cel"]}" stroke-opacity="0.55"/>')
    for k in range(3):
        out.append(f'<circle class="bob" style="animation-delay:{k * 0.15:.2f}s" cx="{372 + k * 15}" cy="113" '
                   f'r="3.8" fill="{P["cel"]}"/>')
    out.append(f'<rect x="418" y="108" width="72" height="10" rx="5" fill="url(#ucstr)"/>')
    # compresión: el razonamiento baja y entra como memoria en el turno 2
    conn = "M400 129 C400 142 382 138 382 152"
    out.append(f'<path d="{conn}" fill="none" stroke="{P["muted"]}" stroke-width="1.6" stroke-dasharray="3 3"/>')
    out.append(packet(conn, P["cel"], 2.4, 0, r=3.4))
    mem, mw = chip(352, 152, "memoria", P, size=13, h=26, pad=10)
    out.append(mem)
    out.append(user_bubble(352 + mw + 8, 152, 530 - (352 + mw + 8)))
    tl1, _ = mono_label("T1", 11, 420, 79, P, anchor="end")
    tl2, _ = mono_label("T2", 11, 530, 146, P, anchor="end")
    out += [tl1, tl2]
    return svg(UW, UH, "".join(out), "CoT-Compress: compresión del razonamiento entre turnos", defs)


def uni_derma(P):
    """DermaVision: una lupa recorre las lesiones; 7 clases, 10.015 imágenes."""
    defs, out = uni_frame(P, P["gold"], "ud", "DermaVision", "Visión artificial · 2026",
                          "Clasifica 7 tipos de lesiones de piel sobre 10.015 imágenes dermatoscópicas.")
    t, wb = text("disp", "0,729", 38, 28, 176, P["text"])
    t2, _ = text("reg", "de macro-F1", 15, 28 + wb + 10, 176, P["muted"])
    out += [t, t2]
    rnd = random.Random(5)
    cells = []
    while len(cells) < 16:
        x, y, r = 372 + rnd.random() * 150, 76 + rnd.random() * 100, 7 + rnd.random() * 9
        if all(math.hypot(x - a, y - b) > r + c + 3 for a, b, c in cells):
            cells.append((x, y, r))
    cols = [P["gold"], P["cel"], P["muted"], P["green"], P["red"], P["text2"], P["cel"]]
    for i, (x, y, r) in enumerate(cells):
        col = cols[i % 7]
        out.append(f'<circle cx="{ntos(x)}" cy="{ntos(y)}" r="{ntos(r)}" fill="{col}" fill-opacity="0.18" '
                   f'stroke="{col}" stroke-opacity="0.55"/>'
                   f'<circle cx="{ntos(x + r * 0.2)}" cy="{ntos(y - r * 0.15)}" r="{ntos(r * 0.32)}" '
                   f'fill="{col}" fill-opacity="0.55"/>')
    # la lupa se queda dentro de la zona de células (sin pisar la etiqueta ni salirse de la tarjeta)
    lens = (f'<g transform="translate(418 112)"><circle r="23" fill="{P["cel"]}" fill-opacity="0.10" '
            f'stroke="{P["text"]}" stroke-width="3"/>'
            f'<line x1="17" y1="17" x2="30" y2="30" stroke="{P["text"]}" stroke-width="5" stroke-linecap="round"/>'
            f'<animateMotion path="M0 0 C30 -22 72 -10 68 22 C64 48 20 56 0 32 C-14 16 -12 8 0 0Z" dur="7s" '
            f'repeatCount="indefinite"/></g>')
    out.append(lens)
    return svg(UW, UH, "".join(out), "DermaVision: clasificación de lesiones de piel", defs)


def wave_path(x0, width, mid, amp, period, noise=None, step=3):
    pts = []
    n = int(width / step) + 1
    for k in range(n):
        x = x0 + k * step
        y = mid + amp * math.sin(2 * math.pi * (x - x0) / period)
        if noise is not None:
            y += noise[k % len(noise)]
        pts.append(f"{ntos(x)} {ntos(y)}")
    return "M" + "L".join(pts)


def uni_clearwave(P):
    """ClearWave: la señal con ruido entra a la U-Net y sale limpia."""
    defs, out = uni_frame(P, P["cel"], "uw", "ClearWave", "Aprendizaje automático · 2025",
                          "Elimina el ruido de la voz con autoencoders y una U-Net.")
    c, _ = chips(28, 150, ["PESQ", "STOI", "LSD", "SDR"], P, size=14, h=26)
    out.append(c)
    x0, w = 352, 180
    defs += f'<clipPath id="uwclip"><rect x="{x0}" y="60" width="{w}" height="136" rx="10"/></clipPath>'
    rnd = random.Random(3)
    noise = [rnd.uniform(-11, 11) for _ in range(20)]  # período de 60 px con paso 3
    noisy = wave_path(x0, w + 60, 92, 9, 60, noise)
    clean = wave_path(x0, w + 60, 166, 14, 60)
    out.append(f'<g clip-path="url(#uwclip)"><g class="flow"><path d="{noisy}" fill="none" stroke="{P["muted"]}" '
               f'stroke-width="2" stroke-linejoin="round"/></g>'
               f'<g class="flow" style="animation-duration:2.4s"><path d="{clean}" fill="none" stroke="{P["cel"]}" '
               f'stroke-width="2.6" stroke-linecap="round"/></g></g>')
    out.append(arrow_down(x0 + w / 2, 114, 142, P["gold"]))
    t, _ = mono_label("U-Net", 13, x0 + w / 2 + 10, 132, P, color=P["gold"])
    l1, _ = mono_label("con ruido", 11, x0 + 2, 70, P)
    l2, _ = mono_label("limpia", 11, x0 + 2, 194, P, color=P["cel"])
    out += [t, l1, l2]
    return svg(UW, UH, "".join(out), "ClearWave: eliminación de ruido en voz", defs)


def uni_pozos(P):
    """Plataforma de pozos: curva de declinación con histórico y pronóstico."""
    defs, out = uni_frame(P, P["gold"], "up", "Plataforma de pozos", "Ing. de software · 2026",
                          "Pronóstico a 60 meses de 4.929 pozos con un modelo Arps + LSTM.")
    c, _ = chips(28, 150, ["Dagster", "dbt", "MLflow", "AWS"], P, size=14, h=26, maxx=340)
    out.append(c)
    ax0, ax1, ay0, ay1 = 362, 530, 72, 176   # área del gráfico
    split = 450

    def curve(x):
        return ay1 - 92 * math.exp(-(x - ax0) / 75)

    hist = [(x, curve(x)) for x in range(ax0, split + 1, 4)]
    fore = [(x, curve(x)) for x in range(split, ax1 + 1, 4)]
    band = ([(x, y - (x - split) * 0.22) for x, y in fore] + [(x, y + (x - split) * 0.22) for x, y in reversed(fore)])
    out.append(f'<line x1="{ax0}" y1="{ay0}" x2="{ax0}" y2="{ay1}" stroke="{P["cardline"]}" stroke-width="1.5"/>'
               f'<line x1="{ax0}" y1="{ay1}" x2="{ax1}" y2="{ay1}" stroke="{P["cardline"]}" stroke-width="1.5"/>')
    out.append(f'<polygon points="{" ".join(f"{ntos(x)},{ntos(y)}" for x, y in band)}" fill="{P["gold"]}" '
               f'fill-opacity="0.16"/>')
    dh = "M" + "L".join(f"{ntos(x)} {ntos(y)}" for x, y in hist)
    df = "M" + "L".join(f"{ntos(x)} {ntos(y)}" for x, y in fore)
    out.append(f'<path d="{dh}" fill="none" stroke="{P["cel"]}" stroke-width="2.4" stroke-linecap="round"/>')
    out.append(f'<path d="{df}" fill="none" stroke="{P["gold"]}" stroke-width="2.4" stroke-linecap="round" '
               f'stroke-dasharray="5 5"/>')
    out.append(f'<line x1="{split}" y1="{ay0 + 6}" x2="{split}" y2="{ay1}" stroke="{P["muted"]}" '
               f'stroke-width="1.2" stroke-dasharray="2 3"/>')
    hoy, _ = mono_label("hoy", 11, split, ay0 + 2, P, anchor="middle")
    pron, _ = mono_label("pronóstico", 11, split + 8, 118, P, color=P["gold"])
    yl, _ = mono_label("producción", 10.5, ax0 - 6, ay0 + 4, P, anchor="end")
    out += [hoy, pron]
    # el punto recorre el histórico y sigue por el pronóstico
    full = dh + "L" + "L".join(f"{ntos(x)} {ntos(y)}" for x, y in fore[1:])
    out.append(f'<circle r="4.5" fill="{P["text"]}" stroke="{P["card"]}" stroke-width="2">'
               f'<animateMotion path="{full}" dur="5s" repeatCount="indefinite" calcMode="linear"/></circle>')
    return svg(UW, UH, "".join(out), "Plataforma predictiva de producción de pozos", defs)


# ---------------------------------------------------------------- pie

def footer(P):
    W, H = 1200, 46
    defs = (f'<linearGradient id="fg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{P["cel"]}"/>'
            f'<stop offset="1" stop-color="{P["gold"]}"/></linearGradient>')
    w1 = wave_path(0, W + 120, 23, 7, 120)
    w2 = wave_path(0, W + 120, 23, 5, 120)
    body = (f'<g><path d="{w1}" fill="none" stroke="url(#fg)" stroke-width="2.6" stroke-linecap="round"/>'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;-120 0" dur="4s" '
            f'repeatCount="indefinite"/></g>'
            f'<g opacity="0.45"><path d="{w2}" fill="none" stroke="url(#fg)" stroke-width="1.6"/>'
            f'<animateTransform attributeName="transform" type="translate" values="-60 0;-180 0" dur="6.5s" '
            f'repeatCount="indefinite"/></g>')
    return svg(W, H, body, "Decoración", defs)


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    builders = {
        "banner": banner,
        "work-pdc": card_pdc,
        "work-llm": card_llm,
        "work-research": card_research,
        "work-infra": card_infra,
        "uni-cot": uni_cot,
        "uni-derma": uni_derma,
        "uni-clearwave": uni_clearwave,
        "uni-pozos": uni_pozos,
        "footer": footer,
    }
    for name, fn in builders.items():
        for theme, P in PAL.items():
            path = out / f"{name}-{theme}.svg"
            path.write_text(fn(P), encoding="utf-8")
            print(f"{path.name}: {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1])
