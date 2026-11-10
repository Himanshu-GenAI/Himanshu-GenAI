#!/usr/bin/env python3
"""
render.py — renders the profile README as a stack of animated SVG cards.

    python render.py             # animated cards  -> cards/*.svg (+ preview.html)
    STATIC=1 python render.py    # final frame only, for screenshots

Every card is a standalone SVG shown through an <img> tag, so it may only use
what survives that sandbox — no scripts, no network, no page-level CSS:

  * one inline <style> block: @font-face, CSS keyframes, media queries
  * fonts subset with pyftsubset and embedded as base64 WOFF data URIs
  * presentation attributes only (no external images, hrefs or <use xlink>)

All motion is CSS keyframes rather than SMIL: SMIL cannot be switched off by a
media query, and every animation has to stop under prefers-reduced-motion.
Elements are authored in their FINAL state and animate *from* a hidden state
with `animation-fill-mode: both`, so a reduced-motion reader (and STATIC=1)
simply sees the finished card.

Colour and type come from himanshu's portfolio: #060913 / #0c1224 surfaces, and a violet -> fuchsia accent ramp
(#8b5cf6 -> #d946ef -> #f472b6) with Inter + JetBrains Mono.

Contribution data is read from data/contributions.json, which
.github/workflows/profile-cards.yml refreshes daily.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import re
import sys
import urllib.request
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from datetime import date, timedelta
from pathlib import Path

from fontTools import subset as ftsubset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parent
CARDS = ROOT / "cards"
CACHE = ROOT / ".cache" / "fonts"
DATA = ROOT / "data" / "contributions.json"

STATIC = os.environ.get("STATIC", "").strip().lower() in {"1", "true", "yes", "on"}

# --------------------------------------------------------------------------- #
# brand tokens — lifted from My_Portfolio/styles.css
# --------------------------------------------------------------------------- #

BG = "#060913"
PANEL = "#0c1224"
PANEL_2 = "#131c38"
TXT = "#f8fafc"
TXT_2 = "#94a3b8"
TXT_3 = "#64748b"
TXT_4 = "#475569"
# accent ramp: violet -> fuchsia -> pink
BRAND = "#8b5cf6"
BRAND_2 = "#d946ef"
BRAND_3 = "#f472b6"
BRAND_SOFT = "#d8b4fe"

FONT_FILES = {
    "Inter": ROOT / "assets" / "fonts" / "Inter-VF.ttf",
    "JBMono": ROOT / "assets" / "fonts" / "JetBrainsMono-VF.ttf",
}

# Fonts and their licences are fetched on first run and pinned by digest, so the
# repo stays text-only and an upstream change fails loudly instead of drifting.
FONT_ASSETS = {
    "Inter-VF.ttf": (
        "https://raw.githubusercontent.com/google/fonts/5bb28733cec313b63fbd415b574b5ae35c8aa8b8/ofl/inter/Inter%5Bopsz,wght%5D.ttf",
        "29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031",
    ),
    "JetBrainsMono-VF.ttf": (
        "https://raw.githubusercontent.com/google/fonts/5bb28733cec313b63fbd415b574b5ae35c8aa8b8/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
        "48715a42ec242c21e9f02692891e147d022299a52e48d5e413e1a942193ffeda",
    ),
    "OFL-Inter.txt": (
        "https://raw.githubusercontent.com/google/fonts/5bb28733cec313b63fbd415b574b5ae35c8aa8b8/ofl/inter/OFL.txt",
        "5b9321a4298cfeb6b34354164a1c3afc3db114569984c502b9b35d988fd58c57",
    ),
    "OFL-JetBrainsMono.txt": (
        "https://raw.githubusercontent.com/google/fonts/5bb28733cec313b63fbd415b574b5ae35c8aa8b8/ofl/jetbrainsmono/OFL.txt",
        "b2fe5e8987594e9ffd1d2ca52a2f5d73eb8335243893c5d6254b5ad69269591d",
    ),
}


def _fetch(url: str, digest: str, dest: Path) -> bytes:
    """Download `url` to `dest` once; verify the pinned digest when given."""
    if dest.exists():
        return dest.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "profile-cards"})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()
    actual = hashlib.sha256(payload).hexdigest()
    if digest and actual != digest:
        raise SystemExit(f"{dest.name}: expected {digest[:12]}… got {actual[:12]}…")
    dest.write_bytes(payload)
    return payload


def ensure_assets() -> None:
    """Fonts (and their OFL licences) are fetched once, then reused from disk."""
    for name, (url, digest) in FONT_ASSETS.items():
        _fetch(url, digest, ROOT / "assets" / "fonts" / name)

# --------------------------------------------------------------------------- #
# copy
# --------------------------------------------------------------------------- #

PROFILE = {
    "name": "Himanshu Rautela",
    "eyebrow": "AI/ML · FRONTEND · DATA",
    "tagline": "CS student at GLA University building AI-powered web apps and data tools.",
    "meta": "MATHURA, INDIA · OPEN TO INTERNSHIPS",
}

TILES = [
    {
        "file": "tile-building",
        "eyebrow": "NOW BUILDING",
        "title": "UniSync.AI",
        "lines": ["College ERP with an AI assistant", "for schedules and attendance."],
        "colour": BRAND,
        "icon": "layers",
    },
    {
        "file": "tile-featured",
        "eyebrow": "FEATURED LIVE",
        "title": "MisInfoX",
        "lines": ["NLP detector for misleading news,", "trained, tuned and deployed."],
        "colour": BRAND_2,
        "icon": "shield",
    },
    {
        "file": "tile-contact",
        "eyebrow": "SAY HELLO",
        "title": "Let's talk",
        "lines": ["Open to data / ML internships", "and frontend work."],
        "colour": BRAND_3,
        "icon": "mail",
    },
]

ICONS = {
    "layers": (
        '<path d="M9 2.2 16.2 5.8 9 9.4 1.8 5.8Z"/>'
        '<path d="M1.8 9.9 9 13.5 16.2 9.9"/>'
        '<path d="M1.8 13.4 9 17 16.2 13.4"/>'
    ),
    "shield": (
        '<path d="M9 1.9 15.6 4.4v4.5c0 4-2.8 6.6-6.6 7.6-3.8-1-6.6-3.6-6.6-7.6V4.4Z"/>'
        '<path d="M6 8.9 8.2 11.1 12.2 6.9"/>'
    ),
    "mail": (
        '<rect x="2.1" y="4.3" width="13.8" height="10.4" rx="2.2"/>'
        '<path d="M3.2 6.1 9 10.4 14.8 6.1"/>'
    ),
}

# featured repos: one card each. `blurb` wins over the repo description so the
# copy stays tight; everything else is read from data/contributions.json.
FEATURED = [
    {
        "repo": "TEAM-ANARCHY-HACKIIITD",
        "blurb": "BidSarthi — an AI copilot that verifies government tender bids against live registries.",
        "link": "https://github.com/Himanshu-GenAI/TEAM-ANARCHY-HACKIIITD",
        "chips": ["Python", "FastAPI", "React"],
    },
    {
        "repo": "ScamShield_AI",
        "blurb": "Real-time scam and phishing detection for the web, built for HackDay 1.0.",
        "link": "https://hackday-1-0.vercel.app",
        "chips": ["TypeScript", "Next.js", "Live demo"],
    },
    {
        "repo": "Secure-Password-Manager",
        "blurb": "Desktop credential vault with PBKDF2 hashing, Fernet encryption and a strong-password generator.",
        "link": "https://github.com/Himanshu-GenAI/Secure-Password-Manager",
        "chips": ["Python", "SQLite", "Cryptography"],
    },
    {
        "repo": "My_Portfolio",
        "blurb": "Portfolio site — glassmorphism dark theme, particle background, hand-written HTML/CSS/JS.",
        "link": "https://my-portfolio-vufh.vercel.app",
        "chips": ["HTML", "CSS", "Live site"],
    },
]


# --------------------------------------------------------------------------- #
# tiny helpers
# --------------------------------------------------------------------------- #


def n(v: float) -> str:
    """Compact number for an SVG attribute."""
    return f"{v:.2f}".rstrip("0").rstrip(".")


def esc(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def thousand(v: int) -> str:
    return f"{v:,}"


def txt(
    x,
    y,
    s,
    *,
    size,
    weight=400,
    family="Inter",
    fill=TXT,
    anchor="start",
    ls=None,
    opacity=None,
    cls=None,
    extra="",
):
    """A <text> element. font-family/weight are always explicit attributes."""
    parts = [
        f'x="{n(x)}"',
        f'y="{n(y)}"',
        f'font-family="{family}"',
        f'font-weight="{weight}"',
        f'font-size="{n(size)}"',
        f'fill="{fill}"',
    ]
    if anchor != "start":
        parts.append(f'text-anchor="{anchor}"')
    if ls is not None:
        parts.append(f'letter-spacing="{n(ls)}"')
    if opacity is not None:
        parts.append(f'opacity="{n(opacity)}"')
    if cls:
        parts.append(f'class="{cls}"')
    if extra:
        parts.append(extra)
    return f'<text {" ".join(parts)}>{esc(s)}</text>'


def panel(x, y, w, h, r=20, fill=PANEL, stroke_opacity=0.08):
    return (
        f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="{n(r)}" '
        f'fill="{fill}" stroke="#ffffff" stroke-opacity="{n(stroke_opacity)}"/>'
    )


def bar_path(x, y, w, h, r):
    """Bar with rounded top corners only."""
    r = max(0.0, min(r, w / 2, h))
    return (
        f"M{n(x)},{n(y + h)}L{n(x)},{n(y + r)}"
        f"Q{n(x)},{n(y)} {n(x + r)},{n(y)}"
        f"L{n(x + w - r)},{n(y)}"
        f"Q{n(x + w)},{n(y)} {n(x + w)},{n(y + r)}"
        f"L{n(x + w)},{n(y + h)}Z"
    )


# --------------------------------------------------------------------------- #
# fonts: instance -> subset (pyftsubset) -> base64 WOFF data URI
# --------------------------------------------------------------------------- #


class FontBook:
    """Builds one tiny WOFF per (family, weight, characters used)."""

    def __init__(self):
        self._instances: dict[tuple[str, int], TTFont] = {}
        self._css: dict[tuple[str, int, str], str] = {}

    def _instance(self, family: str, weight: int) -> TTFont:
        key = (family, weight)
        if key not in self._instances:
            font = TTFont(FONT_FILES[family])
            if "fvar" in font:
                axes = {a.axisTag: a for a in font["fvar"].axes}
                pins = {}
                if "wght" in axes:
                    pins["wght"] = max(
                        axes["wght"].minValue, min(axes["wght"].maxValue, weight)
                    )
                if "opsz" in axes:
                    pins["opsz"] = 16
                font = instancer.instantiateVariableFont(font, pins)
            self._instances[key] = font
        return self._instances[key]

    def width(self, family: str, weight: int, size: float, text: str) -> float:
        """Advance width of `text`, in px, from the instanced font's metrics."""
        font = self._instance(family, weight)
        cmap, hmtx = font.getBestCmap(), font["hmtx"]
        upm = font["head"].unitsPerEm
        total = sum(hmtx[cmap[ord(c)]][0] for c in text if ord(c) in cmap)
        return total / upm * size

    def woff(self, family: str, weight: int, chars: str) -> str:
        digest = hashlib.sha1(
            f"{family}|{weight}|{''.join(sorted(set(chars)))}".encode()
        ).hexdigest()[:16]
        cached = CACHE / f"{family.replace(' ', '')}-{weight}-{digest}.woff"
        if not cached.exists():
            # the subsetter mutates the font, so work on a throwaway copy
            font = copy.deepcopy(self._instance(family, weight))
            opts = ftsubset.Options()
            opts.flavor = "woff"
            opts.name_IDs = [1, 2]
            opts.name_languages = [0x409]
            opts.drop_tables += ["DSIG"]
            opts.hinting = False
            subsetter = ftsubset.Subsetter(options=opts)
            subsetter.populate(text=chars)
            subsetter.subset(font)
            font.flavor = "woff"
            font.recalcTimestamp = False  # byte-stable output
            CACHE.mkdir(parents=True, exist_ok=True)
            font.save(str(cached))
        return base64.b64encode(cached.read_bytes()).decode("ascii")

    def css(self, body: str) -> str:
        """@font-face rules for exactly the families/weights in `body`."""
        pairs = sorted(
            {(fam, int(w)) for fam, w in re.findall(
                r'font-family="([^"]+)" font-weight="(\d+)"', body
            )}
        )
        text = re.sub(r"<[^>]+>", "", body)
        text = (
            text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            .replace("&quot;", '"')
        )
        chars = "".join(sorted(set(text))) + " 0123456789"
        out = []
        for fam, weight in pairs:
            key = (fam, weight, chars)
            if key not in self._css:
                uri = self.woff(fam, weight, chars)
                self._css[key] = (
                    f"@font-face{{font-family:'{fam}';font-style:normal;"
                    f"font-weight:{weight};font-display:block;"
                    f"src:url(data:font/woff;base64,{uri}) format('woff')}}"
                )
            out.append(self._css[key])
        return "".join(out)


BOOK = FontBook()


# --------------------------------------------------------------------------- #
# motion
# --------------------------------------------------------------------------- #

KEYFRAMES = """
.f{animation:fade .85s ease both}
.u{animation:rise .82s cubic-bezier(.22,1,.36,1) both}
.u2{animation:rise2 .8s cubic-bezier(.22,1,.36,1) both}
.gy{animation:growY 1.05s cubic-bezier(.22,1,.36,1) both;transform-box:fill-box;transform-origin:bottom center}
.gyd{animation:growY .9s cubic-bezier(.22,1,.36,1) both;transform-box:fill-box;transform-origin:top center}
.gx{animation:growX .95s cubic-bezier(.22,1,.36,1) both;transform-box:fill-box;transform-origin:left center}
.pp{animation:pop .85s cubic-bezier(.34,1.32,.64,1) both;transform-box:fill-box;transform-origin:center}
.dw{animation:draw 1.6s cubic-bezier(.4,0,.2,1) both}
.pu{animation:pulse 4.2s ease-in-out infinite}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
@keyframes rise2{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}
@keyframes growY{from{transform:scaleY(0);opacity:.25}to{transform:scaleY(1);opacity:1}}
@keyframes growX{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes pop{from{opacity:0;transform:scale(.7)}to{opacity:1;transform:scale(1)}}
@keyframes draw{from{stroke-dashoffset:var(--len,420)}to{stroke-dashoffset:0}}
@keyframes pulse{0%,100%{opacity:.3}50%{opacity:.75}}
"""

# Staggered delays. --o is the card's own start time, set on the root <svg>, so
# cards cascade down the page and each card still animates in order internally.
STEPS = 46
DELAYS = "".join(
    f".s{i}{{animation-delay:calc(var(--o,0s) + {n(i * 0.04)}s)}}"
    for i in range(STEPS)
)

REDUCED = """
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""


def s(step: int) -> str:
    return f"s{max(0, min(STEPS - 1, step))}"


# --------------------------------------------------------------------------- #
# derived contribution numbers
# --------------------------------------------------------------------------- #


def summarise(data: dict) -> dict:
    days = [
        {"date": date.fromisoformat(d["date"]), "count": int(d["count"])}
        for d in data["days"]
    ]
    days.sort(key=lambda d: d["date"])
    total = sum(d["count"] for d in days)
    active = sum(1 for d in days if d["count"] > 0)

    # monthly buckets, in order, trailing 12 months
    buckets: dict[tuple[int, int], int] = {}
    for d in days:
        buckets[(d["date"].year, d["date"].month)] = (
            buckets.get((d["date"].year, d["date"].month), 0) + d["count"]
        )
    months = [
        {"year": y, "month": m, "count": c} for (y, m), c in sorted(buckets.items())
    ][-12:]

    # streaks
    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] > 0 else 0
        longest = max(longest, run)

    current = 0
    tail = list(reversed(days))
    if tail and tail[0]["count"] == 0:
        tail = tail[1:]  # today may simply not have started yet
    for d in tail:
        if d["count"] == 0:
            break
        current += 1

    busiest = max(days, key=lambda d: (d["count"], d["date"])) if days else None
    peak = max((d["count"] for d in days), default=0)

    return {
        "days": days,
        "total": total,
        "active": active,
        "span": len(days),
        "months": months,
        "current_streak": current,
        "longest_streak": longest,
        "busiest": busiest,
        "peak": peak,
        "first": days[0]["date"] if days else None,
        "last": days[-1]["date"] if days else None,
    }


def level_for(count: int, peak: int) -> int:
    if count <= 0:
        return 0
    if peak <= 1:
        return 4
    ratio = count / peak
    if ratio > 0.75:
        return 4
    if ratio > 0.5:
        return 3
    if ratio > 0.25:
        return 2
    return 1


# --------------------------------------------------------------------------- #
# card: hero
# --------------------------------------------------------------------------- #


def portrait_uri(data: dict) -> str | None:
    """A local file wins; otherwise cache the GitHub avatar and embed that.

    The portrait is optional — without either, the hero falls back to a monogram.
    """
    for name in ("portrait.png", "portrait.jpg", "portrait.jpeg", "portrait.webp"):
        path = ROOT / "assets" / name
        if path.exists():
            mime = "png" if path.suffix == ".png" else "webp" if path.suffix == ".webp" else "jpeg"
            return f"data:image/{mime};base64," + base64.b64encode(
                path.read_bytes()
            ).decode("ascii")

    raw = (data.get("profile") or {}).get("avatar_url")
    if not raw:
        return None
    parts = urlsplit(raw)
    query = dict(parse_qsl(parts.query))
    query.setdefault("s", "240")  # the hero circle is 132px; no need for the full avatar
    url = urlunsplit(parts._replace(query=urlencode(query)))
    payload = _fetch(url, "", ROOT / "assets" / "portrait.jpg")
    mime = "png" if payload[:8] == b"\x89PNG\r\n\x1a\n" else "jpeg"
    return f"data:image/{mime};base64," + base64.b64encode(payload).decode("ascii")


def hero(data: dict) -> tuple[int, int, str, str]:
    W, H = 880, 268
    cx, cy, r = 770, 134, 64

    defs = f"""
<defs>
  <clipPath id="panelClip"><rect x="0" y="0" width="{W}" height="{H}" rx="26"/></clipPath>
  <linearGradient id="nameGrad" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#a78bfa"/><stop offset=".5" stop-color="#e879f9"/><stop offset="1" stop-color="#f0abfc"/>
  </linearGradient>
  <linearGradient id="ruleGrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{BRAND}"/><stop offset=".6" stop-color="{BRAND_2}"/><stop offset="1" stop-color="{BRAND_3}" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="ringGrad" gradientUnits="userSpaceOnUse" x1="{cx - r}" y1="{cy - r}" x2="{cx + r}" y2="{cy + r}">
    <stop offset="0" stop-color="{BRAND}"/><stop offset=".5" stop-color="{BRAND_2}"/><stop offset="1" stop-color="{BRAND_3}"/>
  </linearGradient>
  <radialGradient id="glowBrand"><stop offset="0" stop-color="{BRAND}" stop-opacity=".34"/><stop offset="1" stop-color="{BRAND}" stop-opacity="0"/></radialGradient>
  <radialGradient id="glowFuchsia"><stop offset="0" stop-color="{BRAND_3}" stop-opacity=".28"/><stop offset="1" stop-color="{BRAND_3}" stop-opacity="0"/></radialGradient>
  <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">
    <circle cx="1.5" cy="1.5" r="1" fill="#ffffff" opacity=".045"/>
  </pattern>
  <mask id="nameMask" maskUnits="userSpaceOnUse" x="40" y="88" width="540" height="72">
    <rect x="46" y="92" width="530" height="64" fill="#ffffff" class="gx {s(5)}"/>
  </mask>
  <clipPath id="pclip"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>
</defs>"""

    bg = f"""
<g clip-path="url(#panelClip)">
  <rect width="{W}" height="{H}" fill="{BG}"/>
  <ellipse cx="110" cy="-30" rx="330" ry="210" fill="url(#glowBrand)" class="f {s(0)}"/>
  <ellipse cx="810" cy="300" rx="300" ry="200" fill="url(#glowFuchsia)" class="f {s(2)}"/>
  <rect width="{W}" height="{H}" fill="url(#dots)"/>
</g>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="26" fill="none" stroke="#ffffff" stroke-opacity=".09"/>"""

    left = (
        f'<circle cx="55" cy="70" r="2.8" fill="{BRAND_2}" class="pp {s(3)}"/>'
        + txt(66, 74, PROFILE["eyebrow"], size=11, weight=500, family="JBMono",
              fill=BRAND_SOFT, ls=2.4, cls=f"u2 {s(4)}")
        + f'<g mask="url(#nameMask)">'
        + txt(50, 138, PROFILE["name"], size=50, weight=800, fill="url(#nameGrad)", ls=-1.4)
        + "</g>"
        + f'<rect x="52" y="154" width="68" height="3" rx="1.5" fill="url(#ruleGrad)" class="gx {s(9)}"/>'
        + txt(52, 190, PROFILE["tagline"], size=16, weight=500, fill=TXT_2, cls=f"u {s(11)}")
        + txt(52, 226, PROFILE["meta"], size=10.5, weight=400, family="JBMono",
              fill=TXT_3, ls=1.7, cls=f"u2 {s(14)}")
    )

    uri = portrait_uri(data)
    if uri:
        portrait = (
            f'<circle cx="{cx}" cy="{cy}" r="{r + 14}" fill="url(#glowBrand)" class="pu"/>'
            f'<image x="{cx - r}" y="{cy - r}" width="{r * 2}" height="{r * 2}" '
            f'href="{uri}" preserveAspectRatio="xMidYMid slice" clip-path="url(#pclip)" '
            f'class="pp {s(12)}"/>'
        )
    else:
        portrait = (
            f'<circle cx="{cx}" cy="{cy}" r="{r + 14}" fill="url(#glowBrand)" class="pu"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{PANEL_2}" class="pp {s(12)}"/>'
            + txt(cx, cy + 16, "HR", size=44, weight=800, fill="url(#nameGrad)",
                  anchor="middle", ls=-1, cls=f"pp {s(12)}")
        )

    ring = (
        f'<circle cx="{cx}" cy="{cy}" r="{r + 6}" fill="none" stroke="url(#ringGrad)" '
        f'stroke-width="2.5" stroke-linecap="round" stroke-dasharray="{n(2 * 3.14159 * (r + 6))}" '
        f'style="--len:{n(2 * 3.14159 * (r + 6))}" class="dw {s(15)}"/>'
    )

    body = defs + bg + left + portrait + ring
    return W, H, body, f"{PROFILE['name']} — hero"


# --------------------------------------------------------------------------- #
# card: tile (three per row, 32.5% wide)
# --------------------------------------------------------------------------- #


def tile(spec: dict, index: int) -> tuple[int, int, str, str]:
    W, H = 300, 190
    colour = spec["colour"]

    defs = f"""
<defs>
  <clipPath id="tp"><rect x="5" y="5" width="{W - 10}" height="{H - 10}" rx="18"/></clipPath>
  <linearGradient id="tg" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{colour}"/><stop offset=".75" stop-color="{colour}" stop-opacity=".07"/>
  </linearGradient>
</defs>"""

    body = defs + panel(5, 5, W - 10, H - 10, 18) + f"""
<g clip-path="url(#tp)">
  <rect x="5" y="5" width="{W - 10}" height="2.5" fill="url(#tg)" class="gx {s(2)}"/>
</g>
<rect x="22" y="24" width="36" height="36" rx="11" fill="{colour}" fill-opacity=".12"
      stroke="{colour}" stroke-opacity=".3" class="pp {s(4)}"/>
<g transform="translate(31 33)">
  <g fill="none" stroke="{colour}" stroke-width="1.7" stroke-linecap="round"
     stroke-linejoin="round" class="pp {s(6)}">{ICONS[spec['icon']]}</g>
</g>
"""
    body += txt(22, 88, spec["eyebrow"], size=9.5, weight=500, family="JBMono",
                fill=TXT_3, ls=1.7, cls=f"u2 {s(7)}")
    body += txt(22, 114, spec["title"], size=18.5, weight=700, fill=TXT, ls=-0.3,
                cls=f"u {s(9)}")
    for i, line in enumerate(spec["lines"]):
        body += txt(22, 136 + i * 16, line, size=11.5, weight=400, fill=TXT_2,
                    cls=f"u2 {s(11 + i)}")
    body += txt(272, 166, "↗", size=15, weight=400, family="JBMono", fill=colour,
                anchor="end", cls=f"u2 {s(14)}")
    return W, H, body, spec["title"]


# --------------------------------------------------------------------------- #
# card: contributions per month + streak stats
# --------------------------------------------------------------------------- #


def month_label(year: int, month: int) -> str:
    return date(year, month, 1).strftime("%b")


def chart(stats: dict) -> tuple[int, int, str, str]:
    W, H = 880, 396
    x0, x1 = 48, 832
    top, base = 116, 270
    months = stats["months"]
    peak = max((m["count"] for m in months), default=0) or 1
    plot_h = base - top

    defs = f"""
<defs>
  <linearGradient id="barGrad" gradientUnits="userSpaceOnUse" x1="0" y1="{base}" x2="0" y2="{top}">
    <stop offset="0" stop-color="#7c3aed"/><stop offset=".55" stop-color="#c026d3"/>
    <stop offset="1" stop-color="#f472b6"/>
  </linearGradient>
  <linearGradient id="bigGrad" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#c4b5fd"/><stop offset="1" stop-color="#f0abfc"/>
  </linearGradient>
</defs>"""

    body = defs
    body += txt(48, 44, "ACTIVITY", size=10.5, weight=500, family="JBMono", fill=TXT_3,
                ls=2.2, cls=f"u2 {s(1)}")
    body += txt(48, 74, "Contributions per month", size=21, weight=700, fill=TXT, ls=-0.4,
                cls=f"u {s(2)}")
    body += txt(832, 44, "TOTAL", size=10, weight=500, family="JBMono", fill=TXT_3,
                anchor="end", ls=2, cls=f"u2 {s(1)}")
    body += txt(832, 74, thousand(stats["total"]), size=26, weight=700, fill="url(#bigGrad)",
                anchor="end", cls=f"u {s(3)}")
    body += txt(832, 94, "LAST 12 MONTHS", size=9, weight=400, family="JBMono",
                fill=TXT_4, anchor="end", ls=1.9, cls=f"u2 {s(4)}")

    # gridlines
    for frac in (0.25, 0.5, 0.75, 1.0):
        y = base - plot_h * frac
        body += (
            f'<line x1="{x0}" y1="{n(y)}" x2="{x1}" y2="{n(y)}" stroke="#ffffff" '
            f'stroke-opacity=".05" stroke-dasharray="3 7" class="f {s(4)}"/>'
        )

    step = (x1 - x0) / max(1, len(months))
    bw = min(40.0, step * 0.62)
    for i, m in enumerate(months):
        cx = x0 + step * (i + 0.5)
        h = plot_h * (m["count"] / peak)
        h = max(h, 1.5)
        y = base - h
        delay = 6 + i
        body += (
            f'<path d="{bar_path(cx - bw / 2, y, bw, h, 6)}" fill="url(#barGrad)" '
            f'class="gy {s(delay)}"/>'
        )
        if m["count"]:
            body += txt(cx, y - 9, thousand(m["count"]), size=9.5, weight=500,
                        family="JBMono", fill=TXT_2, anchor="middle",
                        cls=f"u2 {s(24 + i)}")
        body += txt(cx, base + 22, month_label(m["year"], m["month"]), size=10,
                    weight=400, family="JBMono", fill=TXT_3, anchor="middle",
                    cls=f"u2 {s(12 + i)}")

    body += (
        f'<rect x="{x0}" y="{base}" width="{x1 - x0}" height="1" fill="#ffffff" '
        f'fill-opacity=".08" class="f {s(6)}"/>'
    )

    # stats
    body += (
        f'<rect x="48" y="308" width="{x1 - x0}" height="1" fill="#ffffff" '
        f'fill-opacity=".07" class="f {s(20)}"/>'
    )
    busiest = stats["busiest"]
    busiest_day = f"{busiest['date']:%b} {busiest['date'].day}, {busiest['date'].year}" if busiest else "—"
    pct = round(100 * stats["active"] / max(1, stats["span"]))
    cells = [
        (
            thousand(stats["current_streak"]),
            "day" if stats["current_streak"] == 1 else "days",
            "CURRENT STREAK",
            f"longest {stats['longest_streak']} days",
        ),
        (thousand(stats["active"]), "", "ACTIVE DAYS", f"{pct}% of {stats['span']} days"),
        (thousand(busiest["count"] if busiest else 0), "", "BUSIEST DAY", busiest_day),
    ]
    for i, (value, unit, label, sub) in enumerate(cells):
        x = 48 + i * 265
        cls = s(30 + i * 2)
        body += txt(x, 352, value, size=27, weight=700, fill=TXT, ls=-0.6, cls=f"u {cls}")
        if unit:
            w = len(value) * 16.5
            body += txt(x + w, 352, unit, size=11.5, weight=500, fill=TXT_3,
                        family="JBMono", cls=f"u {cls}")
        body += txt(x, 370, label, size=9.5, weight=500, family="JBMono", fill=TXT_3,
                    ls=1.7, cls=f"u2 {s(32 + i * 2)}")
        body += txt(x, 386, sub, size=10.5, weight=400, fill=TXT_2, cls=f"u2 {s(33 + i * 2)}")
        if i:
            body += (
                f'<line x1="{n(x - 26)}" y1="330" x2="{n(x - 26)}" y2="382" '
                f'stroke="#ffffff" stroke-opacity=".07" class="f {s(29)}"/>'
            )

    return W, H, body, "contributions per month"


# --------------------------------------------------------------------------- #
# card: one per featured repo
# --------------------------------------------------------------------------- #


def repo_card(spec: dict, index: int, total: int, repos: dict) -> tuple[int, int, str, str]:
    W, H = 880, 146
    meta = repos.get(spec["repo"], {})
    name = meta.get("name") or spec["repo"]
    blurb = spec.get("blurb") or meta.get("description") or "No description yet."
    if len(blurb) > 118:
        blurb = blurb[:115].rstrip(" ,.;:") + "…"
    lang = spec["chips"][0] if spec.get("chips") else (meta.get("language") or "Code")
    dot = (BRAND, BRAND_2, BRAND_3, BRAND_SOFT)[index % 4]

    defs = f"""
<defs>
  <clipPath id="rp"><rect x="0" y="0" width="{W}" height="{H}" rx="20"/></clipPath>
  <linearGradient id="stripe" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{BRAND}"/><stop offset=".55" stop-color="{BRAND_2}"/>
    <stop offset="1" stop-color="{BRAND_3}"/>
  </linearGradient>
  <linearGradient id="nameGradR" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#e2e8f0"/><stop offset="1" stop-color="#f8fafc"/>
  </linearGradient>
</defs>"""

    body = defs + panel(0.5, 0.5, W - 1, H - 1, 20) + f"""
<g clip-path="url(#rp)">
  <rect x="0" y="0" width="4" height="{H}" fill="url(#stripe)" class="gyd {s(2 + index)}"/>
</g>
"""
    body += txt(838, 40, f"0{index + 1} / 0{total}", size=10, weight=400, family="JBMono",
                fill=TXT_4, anchor="end", ls=1.6, cls=f"u2 {s(4)}")
    body += txt(40, 58, name, size=19, weight=700, fill="url(#nameGradR)", ls=-0.4,
                cls=f"u {s(3)}")
    body += txt(40, 86, blurb, size=12.5, weight=400, fill=TXT_2, cls=f"u2 {s(5)}")
    body += (
        f'<line x1="40" y1="106" x2="840" y2="106" stroke="#ffffff" stroke-opacity=".06" '
        f'class="f {s(7)}"/>'
    )
    body += (
        f'<circle cx="43" cy="128" r="3.6" fill="{dot}" class="pp {s(9)}"/>'
        + txt(54, 132, lang, size=11.5, weight=500, fill=TXT_2, cls=f"u2 {s(9)}")
    )
    chips = " · ".join(spec.get("chips", [])[1:]) if len(spec.get("chips", [])) > 1 else ""
    if chips:
        x = 54 + BOOK.width("Inter", 500, 11.5, lang) + 7
        body += txt(x, 132, "· " + chips, size=11.5, weight=400, fill=TXT_3,
                    cls=f"u2 {s(10)}")
    body += txt(838, 132, "OPEN  ↗", size=10.5, weight=500, family="JBMono", fill=BRAND_SOFT,
                anchor="end", ls=1.3, cls=f"u2 {s(12)}")
    return W, H, body, f"{name} — featured repository"


# --------------------------------------------------------------------------- #
# card: contribution graph
# --------------------------------------------------------------------------- #

RAMP = ["#181433", "#4c1d95", "#7c3aed", "#a855f7", "#e879f9"]


def graph(stats: dict) -> tuple[int, int, str, str]:
    W, H = 880, 258
    x0, y0 = 78, 106
    cell, pitch = 11.0, 14.25
    days = stats["days"]
    peak = stats["peak"] or 1

    # sunday-first columns
    first = days[0]["date"]
    origin = first - timedelta(days=(first.weekday() + 1) % 7)
    cols = (days[-1]["date"] - origin).days // 7 + 1
    cols = min(cols, 53)

    body = ""
    body += txt(48, 44, "CONTRIBUTIONS", size=10.5, weight=500, family="JBMono",
                fill=TXT_3, ls=2.2, cls=f"u2 {s(1)}")
    body += txt(48, 74, "Contribution graph", size=21, weight=700, fill=TXT, ls=-0.4,
                cls=f"u {s(2)}")
    body += txt(832, 44, f"{stats['first']:%b %Y} — {stats['last']:%b %Y}".upper(),
                size=9.5, weight=400, family="JBMono", fill=TXT_4, anchor="end", ls=1.8,
                cls=f"u2 {s(1)}")
    body += txt(832, 74, thousand(stats["total"]), size=26, weight=700,
                fill=RAMP[4], anchor="end", cls=f"u {s(3)}")

    for label, row in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        body += txt(x0 - 12, y0 + row * pitch + 8.5, label, size=9, weight=400,
                    family="JBMono", fill=TXT_4, anchor="end", cls=f"u2 {s(6)}")

    # month labels: first column that contains the 1st
    last_month = None
    for day in days:
        if day["date"].day != 1:
            continue
        col = (day["date"] - origin).days // 7
        if col >= cols or col < 1:
            continue
        key = (day["date"].year, day["date"].month)
        if key == last_month:
            continue
        last_month = key
        body += txt(
            x0 + col * pitch, y0 - 9, month_label(*key), size=9, weight=400,
            family="JBMono", fill=TXT_3, cls=f"u2 {s(8)}",
        )

    busiest_date = stats["busiest"]["date"] if stats["busiest"] else None
    for day in days:
        col = (day["date"] - origin).days // 7
        if col >= cols:
            continue
        row = (day["date"].weekday() + 1) % 7
        level = level_for(day["count"], peak)
        x = x0 + col * pitch
        y = y0 + row * pitch
        bucket = min(STEPS - 1, 10 + (col + row) // 2)
        body += (
            f'<rect x="{n(x)}" y="{n(y)}" width="{cell}" height="{cell}" rx="2.6" '
            f'fill="{RAMP[level]}" class="f {s(bucket)}"/>'
        )
        if day["date"] == busiest_date:
            body += (
                f'<rect x="{n(x - 1.6)}" y="{n(y - 1.6)}" width="{n(cell + 3.2)}" '
                f'height="{n(cell + 3.2)}" rx="3.6" fill="none" stroke="#f0abfc" '
                f'stroke-width="1.4" stroke-opacity=".95" class="f {s(STEPS - 3)}"/>'
            )

    # legend
    lx = 832 - (5 * (cell + 3) + 68)
    ly = y0 + 7 * pitch + 18
    body += txt(lx, ly + 9, "Less", size=9, weight=400, family="JBMono", fill=TXT_4,
                cls=f"u2 {s(20)}")
    for i, colour in enumerate(RAMP):
        body += (
            f'<rect x="{n(lx + 34 + i * (cell + 3))}" y="{n(ly)}" width="{cell}" '
            f'height="{cell}" rx="2.6" fill="{colour}" class="f {s(20 + i)}"/>'
        )
    body += txt(lx + 34 + 5 * (cell + 3) + 6, ly + 9, "More", size=9, weight=400,
                family="JBMono", fill=TXT_3, cls=f"u2 {s(22)}")

    return W, H, body, "contribution graph"


# --------------------------------------------------------------------------- #
# assembly
# --------------------------------------------------------------------------- #


def assemble(w: int, h: int, body: str, label: str, offset: float) -> str:
    fonts = BOOK.css(body)
    css = fonts
    if not STATIC:
        css += KEYFRAMES + DELAYS + REDUCED
    style = f"<style>{css}</style>"
    root_style = "" if STATIC else f' style="--o:{n(offset)}s"'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}"{root_style}>'
        f"<title>{esc(label)}</title>{style}{body}</svg>\n"
    )


def preview_page(entries: list[tuple[str, str]]) -> str:
    """A local stand-in for the README so the stack can be eyeballed."""
    hero_file = entries[0][0]
    tiles = entries[1:4]
    rest = entries[4:]
    tile_html = "".join(
        f'<a href="#"><img src="cards/{name}" width="32.5%" alt="{esc(alt)}"></a>'
        for name, alt in tiles
    )
    rest_html = "".join(
        f'<img src="cards/{name}" width="100%" alt="{esc(alt)}">' for name, alt in rest
    )
    mode = "static frame (STATIC=1)" if STATIC else "animated"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>profile cards — {mode}</title>
<style>
  html,body{{margin:0;background:#060913;color:#94a3b8;
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
  .wrap{{max-width:880px;margin:0 auto;padding:40px 16px 64px}}
  img{{display:block;max-width:100%;height:auto;border:0}}
  .tiles{{display:flex;justify-content:center;align-items:flex-start;margin:14px 0}}
  .tiles a{{display:block;width:32.5%;text-decoration:none}}
  .tiles img{{width:100%;height:auto}}
  .stack>*+*{{margin-top:14px}}
  p.note{{font-size:12px;color:#475569;margin:0 0 18px}}
</style></head>
<body><div class="wrap">
<p class="note">Local preview — {mode}. This file is not referenced by README.md.</p>
<div class="stack">
<img src="cards/{hero_file}" width="100%" alt="hero">
<div class="tiles">{tile_html}</div>
{rest_html}
</div></div></body></html>
"""


def main() -> None:
    if not DATA.exists():
        raise SystemExit(
            f"missing {DATA.relative_to(ROOT)} — run scripts/fetch_contributions.py first"
        )
    data = json.loads(DATA.read_text(encoding="utf-8"))
    ensure_assets()
    stats = summarise(data)
    repos = {r["name"]: r for r in data.get("repos", [])}

    CARDS.mkdir(parents=True, exist_ok=True)
    rendered: list[tuple[str, int, int, str, str]] = []

    rendered.append(("hero", *hero(data)))
    for i, spec in enumerate(TILES):
        rendered.append((spec["file"], *tile(spec, i)))
    rendered.append(("chart", *chart(stats)))
    for i, spec in enumerate(FEATURED):
        rendered.append(
            (f"repo-{slug(spec['repo'])}", *repo_card(spec, i, len(FEATURED), repos))
        )
    rendered.append(("graph", *graph(stats)))

    written = []
    for index, (name, w, h, body, label) in enumerate(rendered):
        offset = index * 0.1
        svg = assemble(w, h, body, label, offset)
        path = CARDS / f"{name}.svg"
        path.write_text(svg, encoding="utf-8")
        written.append((path.name, label))

    (ROOT / "preview.html").write_text(preview_page(written), encoding="utf-8")

    total = sum(p.stat().st_size for p in CARDS.glob("*.svg"))
    mode = "static" if STATIC else "animated"
    print(f"✓ {len(written)} cards ({mode}) → cards/  {total / 1024:.0f} kB total")
    for name, _ in written:
        print(f"   cards/{name}  {(CARDS / name).stat().st_size / 1024:5.1f} kB")


if __name__ == "__main__":
    main()
