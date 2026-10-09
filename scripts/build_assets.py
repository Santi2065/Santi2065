#!/usr/bin/env python3
"""Genera los SVG animados del README de perfil de GitHub.

Todo el texto se convierte en trazos (paths) con HarfBuzz + fontTools, así se ve
igual en cualquier sistema sin depender de fuentes instaladas. Las animaciones
usan CSS y SMIL, que GitHub muestra en imágenes SVG.

Uso: python3 scripts/build_assets.py assets
Requiere: pip install uharfbuzz fonttools brotli; fuentes Inter y JetBrains Mono
(INTER_DIR y MONO_DIR para indicar dónde están).
"""
import io
import os
import math
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
                 gold="#f6c453", green="#3ddc97", grid="#1c2a44", chip="#152238",
                 chipline="#253753", chiptext="#cfe1f5", inner="#0b1322",
                 glowA=0.24, glowB=0.13),
    "light": dict(bg0="#ffffff", bg1="#ebf4fe", card="#ffffff", cardline="#d3e1f1",
                  text="#0d1a2c", text2="#3b4b61", muted="#687a92", cel="#1a72d6",
                  gold="#b8790c", green="#14965a", grid="#dce7f4", chip="#edf4fc",
                  chipline="#d0dff1", chiptext="#1b3a5e", inner="#f3f8fd",
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
.ping{opacity:0;animation:ping 3s linear infinite}
@keyframes ping{0%{opacity:1}35%{opacity:0}100%{opacity:0}}
.scan{animation:scan 3s linear infinite}
@keyframes scan{from{transform:translateX(0)}to{transform:translateX(150px)}}
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


def card_frame(w, h, P, accent, uid, gx=0.9, gy=0.0):
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


def chip(x, y, label, P, size=15, h=28, pad=11):
    w = F["mono"].width(label, size) + 2 * pad
    t, _ = text("mono", label, size, x + pad, y + h / 2 + size * 0.36, P["chiptext"])
    return (f'<rect x="{ntos(x)}" y="{y}" width="{ntos(w)}" height="{h}" rx="{h / 2}" '
            f'fill="{P["chip"]}" stroke="{P["chipline"]}"/>' + t), w


def chips(x, y, labels, P, size=15, h=28, gap=8, maxx=None):
    out, cx = [], x
    for lab in labels:
        s, w = chip(cx, y, lab, P, size, h)
        if maxx is not None and cx + w > maxx:
            break
        out.append(s)
        cx += w + gap
    return "".join(out), cx - gap


# ---------------------------------------------------------------- íconos

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


def icon_lock(cx, cy, c):
    return (f'<g fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round">'
            f'<rect x="{cx - 6}" y="{cy - 2}" width="12" height="10" rx="2.2"/>'
            f'<path d="M{cx - 3.6} {cy - 2}v-3a3.6 3.6 0 0 1 7.2 0v3"/></g>')


def icon_check(cx, cy, c):
    return (f'<circle cx="{cx}" cy="{cy}" r="8" fill="{c}" fill-opacity="0.15"/>'
            f'<path d="M{cx - 3.6} {cy}l2.4 2.6l4.8-5.2" fill="none" stroke="{c}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')


def icon_refresh(cx, cy, r, c):
    # arco de 300 grados con punta de flecha, gira despacio
    a0, a1 = math.radians(-60), math.radians(240)
    x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
    x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
    tip = (f'M{ntos(x0 - 5)} {ntos(y0 - 1)}L{ntos(x0 + 1)} {ntos(y0 + 1)}L{ntos(x0 - 1)} {ntos(y0 - 6)}')
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
    return (f'<circle r="{r}" fill="{c}" opacity="0">'
            f'<animateMotion path="{path}" dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.15;0.8;1" '
            f'dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/></circle>')


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
    t, _ = text("med", "Desarrollador de software e IA", 27, 66, 205, P["text2"])
    body.append(t)
    t, wp = text("monob", "$", 21, 66, 256, P["gold"])
    body.append(t)
    x0 = 66 + F["mono"].width("$ ", 21)
    tdefs, tbody = typewriter(PHRASES, x0, 256, 21, P)
    defs.append(tdefs)
    body.append(tbody)

    # pipeline vertical: datos -> modelos -> producción
    bx, bw, bh = 914, 240, 58
    ys = [36, 131, 226]
    labels = ["datos", "modelos", "producción"]
    icons = [icon_db, icon_net, None]
    for i, (y, lab) in enumerate(zip(ys, labels)):
        last = i == 2
        stroke = P["gold"] if last else P["cardline"]
        body.append(f'<rect x="{bx}" y="{y}" width="{bw}" height="{bh}" rx="14" fill="{P["card"]}" '
                    f'fill-opacity="0.9" stroke="{stroke}" stroke-width="{2 if last else 1.5}"/>')
        cy = y + bh / 2
        if last:
            body.append(icon_server(bx + 34, cy, P["gold"], P["green"]))
        else:
            body.append(icons[i](bx + 34, cy, P["cel"]))
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
                body.append(packet(f"M{ax} {y1} L{ax} {y2 - 6}", P["cel"], 1.4, k * 0.7 + i * 0.35, r=3.6))
    label = "Santiago Groba Alonso — Desarrollador de software e IA"
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


def stat(x, y, big, label, P, unit=None):
    out = []
    t, wb = text("disp", big, 50, x, y, P["text"])
    out.append(t)
    wu = 0
    if unit:
        t, wu = text("dispsemi", unit, 26, x + wb + 6, y, P["text2"])
        out.append(t)
        wu += 6
    t, wl = text("reg", label, 15, x + 2, y + 26, P["muted"])
    out.append(t)
    return "".join(out), max(wb + wu, wl), wb + wu


def card_pdc(P):
    defs, frame = card_frame(CW, CH, P, P["gold"], "p", gx=0.95, gy=0.05)
    out = [frame, card_head(P, "PrecioDelDolarCo", "Comparador de tasas de cambio en Colombia")]
    out.append(badge(530, 33, "en producción", P["green"], P, pulse=True))
    s1, w1, _ = stat(30, 156, "1.179", "casas de cambio", P)
    out.append(s1)
    x2 = 30 + w1 + 36
    s2, w2, wbig = stat(x2, 156, "30", "entre actualizaciones", P, unit="min")
    out.append(s2)
    out.append(icon_refresh(x2 + wbig + 22, 145, 9, P["gold"]))

    # "radar" del scraper: puntos que se encienden cuando pasa la línea
    rx0, ry0, rw, rh = 382, 104, 150, 104
    ecx, ecy = rx0 + rw / 2, ry0 + rh / 2
    defs += (f'<clipPath id="pradar"><ellipse cx="{ecx}" cy="{ecy}" rx="{rw / 2}" ry="{rh / 2}"/></clipPath>'
             f'<linearGradient id="ptrail" x1="0" y1="0" x2="1" y2="0">'
             f'<stop offset="0" stop-color="{P["gold"]}" stop-opacity="0"/>'
             f'<stop offset="1" stop-color="{P["gold"]}" stop-opacity="0.22"/></linearGradient>')
    rnd = random.Random(11)
    pts = []
    while len(pts) < 38:
        x, y = rx0 + 10 + rnd.random() * (rw - 20), ry0 + 8 + rnd.random() * (rh - 16)
        if ((x - ecx) / (rw / 2 - 8)) ** 2 + ((y - ecy) / (rh / 2 - 8)) ** 2 <= 1:
            pts.append((x, y))
    out.append(f'<ellipse cx="{ecx}" cy="{ecy}" rx="{rw / 2}" ry="{rh / 2}" fill="{P["inner"]}" '
               f'stroke="{P["cardline"]}" stroke-dasharray="4 5"/>')
    g = [f'<g clip-path="url(#pradar)">']
    for x, y in pts:
        g.append(f'<circle cx="{ntos(x)}" cy="{ntos(y)}" r="2.6" fill="{P["muted"]}" fill-opacity="0.5"/>')
    for x, y in pts:
        delay = (x - rx0) / rw * 3
        g.append(f'<circle class="ping" style="animation-delay:{delay:.2f}s" cx="{ntos(x)}" cy="{ntos(y)}" '
                 f'r="3.4" fill="{P["gold"]}"/>')
    g.append(f'<g class="scan"><rect x="{rx0 - 40}" y="{ry0}" width="40" height="{rh}" fill="url(#ptrail)"/>'
             f'<line x1="{rx0}" y1="{ry0}" x2="{rx0}" y2="{ry0 + rh}" stroke="{P["gold"]}" stroke-width="2"/></g>')
    g.append("</g>")
    out.append("".join(g))

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


def gpu(x, y, w, h, P, durs):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{P["inner"]}" '
           f'stroke="{P["cardline"]}" stroke-width="1.5"/>']
    for i, fx in enumerate([x + w * 0.3, x + w * 0.7]):
        fy, r = y + h / 2, h * 0.36
        out.append(f'<circle cx="{ntos(fx)}" cy="{ntos(fy)}" r="{ntos(r + 2)}" fill="none" '
                   f'stroke="{P["cardline"]}" stroke-width="1.5"/>')
        out.append(f'<g transform="translate({ntos(fx)} {ntos(fy)})"><g class="spin" '
                   f'style="animation-duration:{durs[i]}s">{blades(r, P["cel"])}</g></g>')
        out.append(f'<circle cx="{ntos(fx)}" cy="{ntos(fy)}" r="{ntos(r * 0.24)}" fill="{P["muted"]}"/>')
    for k in range(9):
        out.append(f'<rect x="{ntos(x + w * 0.18 + k * 9)}" y="{y + h}" width="5" height="5" '
                   f'fill="{P["gold"]}" fill-opacity="0.85"/>')
    return "".join(out)


def card_llm(P):
    defs, frame = card_frame(CW, CH, P, P["cel"], "l", gx=0.95, gy=0.05)
    out = [frame, card_head(P, "LLM on-premise", "Para el archivo de escrituras de una escribanía")]
    out.append(badge(530, 33, "en producción", P["green"], P, pulse=True))
    s1, _, _ = stat(30, 156, "27B", "parámetros · Qwen 3.6 · 2× RTX 3090", P)
    out.append(s1)
    out.append(icon_lock(37, 205, P["muted"]))
    t, _ = text("reg", "los documentos no salen de la oficina", 15, 52, 211, P["muted"])
    out.append(t)
    out.append(gpu(338, 104, 192, 50, P, (0.9, 1.15)))
    out.append(gpu(338, 168, 192, 50, P, (1.05, 0.8)))
    c, _ = chips(30, 238, ["vLLM", "Qdrant", "PostgreSQL", "RAG"], P, maxx=530)
    out.append(c)
    return svg(CW, CH, "".join(out), "LLM on-premise: Qwen 3.6 27B en dos RTX 3090", defs)


def card_research(P):
    defs, frame = card_frame(CW, CH, P, P["cel"], "r", gx=0.95, gy=0.05)
    out = [frame, card_head(P, "Investigación", "¿Preservar o descartar el razonamiento de un LLM entre turnos?")]
    out.append(badge(530, 33, "paper en preparación", P["cel"], P))
    defs += (f'<pattern id="rstr" width="9" height="9" patternUnits="userSpaceOnUse" '
             f'patternTransform="rotate(45)"><rect width="9" height="9" fill="{P["cel"]}" fill-opacity="0.22"/>'
             f'<rect width="3.5" height="9" fill="{P["cel"]}" fill-opacity="0.75"/></pattern>')

    def bubble(x, label):
        t, _ = text("monob", label, 17, x + 28, 150, P["text"], anchor="middle")
        return (f'<rect x="{x}" y="122" width="56" height="42" rx="12" fill="{P["chip"]}" '
                f'stroke="{P["chipline"]}" stroke-width="1.5"/>' + t)

    out.append(bubble(30, "T1"))
    tx, tw, ty, th = 102, 330, 133, 20
    out.append(f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="10" fill="{P["inner"]}" '
               f'stroke="{P["cardline"]}" stroke-dasharray="4 4"/>')
    out.append(f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="10" fill="url(#rstr)">'
               f'<animate attributeName="width" values="{tw};{tw};128;128;14;14;{tw}" '
               f'keyTimes="0;0.30;0.36;0.62;0.68;0.93;1" dur="7.5s" repeatCount="indefinite"/></rect>')
    out.append(arrow_right(tx + tw + 8, 470, ty + th / 2, P["muted"]))
    out.append(bubble(474, "T2"))
    states = [("preservar: todo el razonamiento", "0;0.30;0.33;0.95;0.98;1", "1;1;0;0;1;1"),
              ("comprimir: un resumen", "0;0.33;0.36;0.62;0.65;1", "0;0;1;1;0;0"),
              ("descartar: nada", "0;0.65;0.68;0.93;0.96;1", "0;0;1;1;0;0")]
    for i, (lab, kt, vals) in enumerate(states):
        d, _ = F["mono"].d(lab, 15, tx, 190)
        out.append(f'<path d="{d}" fill="{P["text2"]}" opacity="{1 if i == 0 else 0}">'
                   f'<animate attributeName="opacity" values="{vals}" keyTimes="{kt}" dur="7.5s" '
                   f'repeatCount="indefinite"/></path>')
    link, wl = text("med", "CoT-Compress ↗", 15, 530, 257, P["cel"], anchor="end")
    t, _ = text("mono", "con J. Wisznia y L. Del Corro (UdeSA)", 14, 30, 257, P["muted"])
    out += [t, link]
    return svg(CW, CH, "".join(out), "Investigación: razonamiento de LLMs, paper en preparación", defs)


def pc_icon(cx, cy, P):
    return (f'<rect x="{ntos(cx - 13)}" y="{ntos(cy - 10)}" width="26" height="17" rx="3" fill="{P["inner"]}" '
            f'stroke="{P["text2"]}" stroke-width="1.6"/>'
            f'<line x1="{ntos(cx)}" y1="{ntos(cy + 7)}" x2="{ntos(cx)}" y2="{ntos(cy + 11)}" '
            f'stroke="{P["text2"]}" stroke-width="1.6"/>'
            f'<line x1="{ntos(cx - 6)}" y1="{ntos(cy + 11.5)}" x2="{ntos(cx + 6)}" y2="{ntos(cy + 11.5)}" '
            f'stroke="{P["text2"]}" stroke-width="1.6" stroke-linecap="round"/>')


def card_infra(P):
    defs, frame = card_frame(CW, CH, P, P["green"], "i", gx=0.95, gy=0.05)
    out = [frame, card_head(P, "Infraestructura", "Escribanías y estudios de Buenos Aires")]
    out.append(badge(530, 33, "desde 2020", P["text2"], P))
    items = ["Soporte remoto de equipos", "Redes, backups y acceso remoto", "Renovación de hardware"]
    for k, it in enumerate(items):
        y = 132 + k * 32
        out.append(icon_check(38, y - 5, P["green"]))
        t, _ = text("reg", it, 16, 56, y, P["text2"])
        out.append(t)
    sx, sy = 488, 160
    pcs = [(374, 110 + k * 33) for k in range(4)]
    for px, py in pcs:
        out.append(f'<path d="M{sx - 17} {sy}C{sx - 60} {sy} {px + 50} {py} {px + 15} {py}" fill="none" '
                   f'stroke="{P["cardline"]}" stroke-width="1.6"/>')
    for k, (px, py) in enumerate(pcs):
        out.append(packet(f"M{sx - 17} {sy}C{sx - 60} {sy} {px + 50} {py} {px + 15} {py}", P["green"], 1.6,
                          k * 0.4, r=3.2))
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
    defs, out = uni_frame(P, P["cel"], "uc", "CoT-Compress", "NLP · 2026",
                          "Chat local que comprime el razonamiento del modelo y lo reinyecta como memoria.")
    t, wb = text("disp", "6", 38, 28, 176, P["text"])
    t2, _ = text("reg", "estrategias de compresión", 15, 28 + wb + 10, 176, P["muted"])
    out += [t, t2]
    # burbuja del usuario, burbuja "pensando" y memoria
    out.append(f'<rect x="414" y="70" width="116" height="30" rx="15" fill="{P["chip"]}" stroke="{P["chipline"]}"/>'
               f'<line x1="430" y1="85" x2="512" y2="85" stroke="{P["text2"]}" stroke-width="3" '
               f'stroke-linecap="round" stroke-opacity="0.5"/>')
    out.append(f'<rect x="356" y="112" width="124" height="34" rx="17" fill="{P["cel"]}" fill-opacity="0.14" '
               f'stroke="{P["cel"]}" stroke-opacity="0.55"/>')
    for k in range(3):
        out.append(f'<circle class="bob" style="animation-delay:{k * 0.15:.2f}s" cx="{402 + k * 16}" cy="129" '
                   f'r="4.2" fill="{P["cel"]}"/>')
    out.append(arrow_down(418, 150, 168, P["muted"]))
    mw = F["mono"].width("memoria", 14) + 22
    mem, _ = chip(418 - mw / 2, 170, "memoria", P, size=14, h=26)
    out.append(mem)
    return svg(UW, UH, "".join(out), "CoT-Compress: compresión del razonamiento entre turnos", defs)


def uni_derma(P):
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
    for i, (x, y, r) in enumerate(cells):
        col = [P["gold"], P["cel"], P["muted"]][i % 3]
        out.append(f'<circle cx="{ntos(x)}" cy="{ntos(y)}" r="{ntos(r)}" fill="{col}" fill-opacity="0.18" '
                   f'stroke="{col}" stroke-opacity="0.55"/>'
                   f'<circle cx="{ntos(x + r * 0.2)}" cy="{ntos(y - r * 0.15)}" r="{ntos(r * 0.32)}" '
                   f'fill="{col}" fill-opacity="0.55"/>')
    lens = (f'<g transform="translate(420 110)"><circle r="25" fill="{P["cel"]}" fill-opacity="0.10" stroke="{P["text"]}" stroke-width="3"/>'
            f'<line x1="18" y1="18" x2="34" y2="34" stroke="{P["text"]}" stroke-width="5" stroke-linecap="round"/>'
            f'<animateMotion path="M0 0 C40 -40 100 -20 80 30 C60 70 -20 60 0 0Z" dur="7s" '
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
    defs, out = uni_frame(P, P["cel"], "uw", "ClearWave", "Aprendizaje automático · 2025",
                          "Elimina el ruido de la voz con autoencoders y una U-Net.")
    c, _ = chips(28, 150, ["PESQ", "STOI", "LSD", "SDR"], P, size=14, h=26)
    out.append(c)
    x0, w = 352, 180
    defs += f'<clipPath id="uwclip"><rect x="{x0}" y="56" width="{w}" height="140" rx="10"/></clipPath>'
    rnd = random.Random(3)
    noise = [rnd.uniform(-11, 11) for _ in range(20)]  # período de 60 px con paso 3
    noisy = wave_path(x0, w + 60, 92, 9, 60, noise)
    clean = wave_path(x0, w + 60, 166, 14, 60)
    out.append(f'<g clip-path="url(#uwclip)"><g class="flow"><path d="{noisy}" fill="none" stroke="{P["muted"]}" '
               f'stroke-width="2" stroke-linejoin="round"/></g>'
               f'<g class="flow" style="animation-duration:2.4s"><path d="{clean}" fill="none" stroke="{P["cel"]}" '
               f'stroke-width="2.6" stroke-linecap="round"/></g></g>')
    out.append(arrow_down(x0 + w / 2, 112, 140, P["gold"]))
    t, _ = text("mono", "U-Net", 13, x0 + w / 2 + 10, 131, P["gold"])
    out.append(t)
    return svg(UW, UH, "".join(out), "ClearWave: eliminación de ruido en voz", defs)


def uni_pozos(P):
    defs, out = uni_frame(P, P["gold"], "up", "Plataforma de pozos", "Ing. de software · 2026",
                          "Pipeline de datos y API de pronóstico de producción de petróleo.")
    c, _ = chips(28, 150, ["Dagster", "dbt", "MLflow", "AWS"], P, size=14, h=26, maxx=340)
    out.append(c)
    g = 186  # suelo
    px, py = 456, 98  # pivote del balancín
    out.append(f'<line x1="360" y1="{g}" x2="536" y2="{g}" stroke="{P["cardline"]}" stroke-width="2"/>')
    # caballete
    out.append(f'<path d="M436 {g}L{px} {py + 4}L476 {g}" fill="none" stroke="{P["text2"]}" stroke-width="3" '
               f'stroke-linejoin="round"/>')
    # boca de pozo y varilla
    out.append(f'<rect x="384" y="{g - 12}" width="14" height="12" rx="2" fill="{P["text2"]}"/>'
               f'<line x1="391" y1="{py + 18}" x2="391" y2="{g - 12}" stroke="{P["muted"]}" stroke-width="2"/>')
    # manivela con contrapeso girando
    out.append(f'<g transform="translate(508 160)"><g class="spin-slow" style="animation-duration:2.6s">'
               f'<circle r="16" fill="none"/><rect x="-4" y="-16" width="8" height="32" rx="3" fill="{P["gold"]}"/>'
               f'<circle r="5" fill="{P["text2"]}"/></g></g>')
    out.append(f'<line x1="496" y1="{g}" x2="508" y2="160" stroke="{P["text2"]}" stroke-width="3"/>'
               f'<line x1="520" y1="{g}" x2="508" y2="160" stroke="{P["text2"]}" stroke-width="3"/>')
    # balancín con cabeza de caballo, cabecea sobre el pivote
    beam = (f'<g><line x1="396" y1="{py}" x2="524" y2="{py}" stroke="{P["text"]}" stroke-width="6" '
            f'stroke-linecap="round"/>'
            f'<path d="M398 {py - 14}Q378 {py} 398 {py + 18}L404 {py + 18}Q392 {py} 404 {py - 14}Z" '
            f'fill="{P["text"]}"/>'
            f'<line x1="508" y1="{py}" x2="508" y2="146" stroke="{P["text2"]}" stroke-width="3"/>'
            f'<circle cx="{px}" cy="{py}" r="5" fill="{P["gold"]}"/>'
            f'<animateTransform attributeName="transform" type="rotate" '
            f'values="-9 {px} {py};9 {px} {py};-9 {px} {py}" dur="2.6s" repeatCount="indefinite" '
            f'calcMode="spline" keyTimes="0;0.5;1" keySplines=".45 0 .55 1;.45 0 .55 1"/></g>')
    out.append(beam)
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
            f'<g opacity="0.45"><path d="{w2}" fill="none" stroke="url(#fg)" stroke-width="1.6" '
            f'transform="translate(-60 0)"/>'
            f'<animateTransform attributeName="transform" type="translate" values="0 0;-120 0" dur="6.5s" '
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
