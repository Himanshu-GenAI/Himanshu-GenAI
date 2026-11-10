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
