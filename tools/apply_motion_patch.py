#!/usr/bin/env python3
"""One-shot: apply this session's renderer changes to render.py.

Deleted in the same commit that runs it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "render.py"

PAIRS = []

# 1. new motion classes on the shared keyframe sheet
PAIRS.append((
    '''.pu{animation:pulse 4.2s ease-in-out infinite}
@keyframes fade{from{opacity:0}to{opacity:1}}''',
    '''.pu{animation:pulse 4.2s ease-in-out infinite}
.sw{animation:swing 1.15s cubic-bezier(.22,1,.36,1) both;transform-box:fill-box;transform-origin:bottom center}
.sh{animation:shine 7.5s ease-in-out 1.2s infinite}
.tsh{animation:tshine 6.5s ease-in-out infinite}
.rp{animation:ring 4s ease-out 1s infinite;transform-box:fill-box;transform-origin:center}
.ar{animation:nudge 3.4s ease-in-out infinite}
@keyframes fade{from{opacity:0}to{opacity:1}}''',
))

# 2. the new keyframes themselves
PAIRS.append((
    '''@keyframes pulse{0%,100%{opacity:.3}50%{opacity:.75}}
''',
    '''@keyframes pulse{0%,100%{opacity:.3}50%{opacity:.75}}
@keyframes swing{from{opacity:0;transform:translateY(22px) rotate(-2.4deg) scale(.96)}60%{opacity:1;transform:translateY(-2px) rotate(.8deg) scale(1.004)}to{opacity:1;transform:translateY(0) rotate(0deg) scale(1)}}
@keyframes shine{0%{transform:translateX(-260px) skewX(-16deg);opacity:0}6%{opacity:.85}26%{opacity:.85}34%,100%{transform:translateX(1200px) skewX(-16deg);opacity:0}}
@keyframes tshine{0%{transform:translateX(0) skewX(-12deg);opacity:0}5%{opacity:.34}24%{opacity:.34}30%,100%{transform:translateX(430px) skewX(-12deg);opacity:0}}
@keyframes ring{0%{opacity:.45;transform:scale(1)}70%,100%{opacity:0;transform:scale(1.85)}}
@keyframes nudge{0%,100%{transform:translate(0,0)}50%{transform:translate(3px,-3px)}}
''',
))

# 3. hero: a shine band clipped to the name
PAIRS.append((
    '''  <mask id="nameMask" maskUnits="userSpaceOnUse" x="40" y="88" width="540" height="72">''',
    '''  <linearGradient id="shineGrad" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0"/><stop offset=".5" stop-color="#ffffff" stop-opacity=".85"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>
  <clipPath id="nameClip">{txt(50, 138, PROFILE['name'], size=50, weight=800, ls=-1.4)}</clipPath>
  <mask id="nameMask" maskUnits="userSpaceOnUse" x="40" y="88" width="540" height="72">''',
))

# 4. hero: the sweeping band itself, authored hidden
PAIRS.append((
    '''        + txt(50, 138, PROFILE["name"], size=50, weight=800, fill="url(#nameGrad)", ls=-1.4)
        + "</g>"''',
    '''        + txt(50, 138, PROFILE["name"], size=50, weight=800, fill="url(#nameGrad)", ls=-1.4)
        + '<g clip-path="url(#nameClip)"><rect x="-40" y="82" width="200" height="74" '
          'fill="url(#shineGrad)" opacity="0" class="sh"/></g>'
        + "</g>"''',
))

# 5. hero: the eyebrow dot pulses instead of just popping in
PAIRS.append((
    '''        f'<circle cx="55" cy="70" r="2.8" fill="{BRAND_2}" class="pp {s(3)}"/>'
''',
    '''        f'<circle cx="55" cy="70" r="2.8" fill="{BRAND_2}" class="pu {s(3)}"/>'
''',
))

# 6. tile: gradient for the sweep
PAIRS.append((
    '''  <linearGradient id="tg" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{colour}"/><stop offset=".75" stop-color="{colour}" stop-opacity=".07"/>
  </linearGradient>''',
    '''  <linearGradient id="tg" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{colour}"/><stop offset=".75" stop-color="{colour}" stop-opacity=".07"/>
  </linearGradient>
  <linearGradient id="tshine" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0"/><stop offset=".5" stop-color="#ffffff" stop-opacity=".55"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>''',
))

# 7. tile: swing-in group, pulsing corner ring, sweep band, nudging arrow
PAIRS.append((
    '''    body = defs + panel(5, 5, W - 10, H - 10, 18) + f"""
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
    body += txt(272, 166, "\u2197", size=15, weight=400, family="JBMono", fill=colour,
                anchor="end", cls=f"u2 {s(14)}")
    return W, H, body, spec["title"]''',
    '''    # the whole tile tilts up and settles; the badge ring pulses out of the
    # icon corner and a light band sweeps the card every few seconds
    inner = f"""
  <circle cx="40" cy="42" r="18" fill="none" stroke="{colour}" stroke-width="2"
          opacity="0" class="rp"/>
  <rect x="22" y="24" width="36" height="36" rx="11" fill="{colour}" fill-opacity=".12"
        stroke="{colour}" stroke-opacity=".3" class="pp {s(4)}"/>
  <g transform="translate(31 33)">
    <g fill="none" stroke="{colour}" stroke-width="1.7" stroke-linecap="round"
       stroke-linejoin="round" class="pp {s(6)}">{ICONS[spec['icon']]}</g>
  </g>"""
    inner += txt(22, 88, spec["eyebrow"], size=9.5, weight=500, family="JBMono",
                 fill=TXT_3, ls=1.7, cls=f"u2 {s(7)}")
    inner += txt(22, 114, spec["title"], size=18.5, weight=700, fill=TXT, ls=-0.3,
                 cls=f"u {s(9)}")
    for i, line in enumerate(spec["lines"]):
        inner += txt(22, 136 + i * 16, line, size=11.5, weight=400, fill=TXT_2,
                     cls=f"u2 {s(11 + i)}")
    inner += txt(272, 166, "\u2197", size=15, weight=400, family="JBMono", fill=colour,
                 anchor="end", cls=f"ar {s(15)}")
    body = defs + panel(5, 5, W - 10, H - 10, 18) + f"""
<g clip-path="url(#tp)">
  <rect x="5" y="5" width="{W - 10}" height="2.5" fill="url(#tg)" class="gx {s(2)}"/>
  <rect x="-70" y="5" width="46" height="{H - 10}" fill="url(#tshine)" opacity="0" class="tsh"/>
</g>
<g class="sw {s(3)}">{inner}</g>"""
    return W, H, body, spec["title"]''',
))

# 8. layout order: face, graph, monthly bars, tiles, repos
PAIRS.append((
    '''    rendered.append(("hero", *hero(data)))
    for i, spec in enumerate(TILES):
        rendered.append((spec["file"], *tile(spec, i)))
    rendered.append(("chart", *chart(stats)))''',
    '''    # layout follows the reference build: face, then the graph and the monthly
    # bars right under it, then the colourful tiles, then what he is coding
    rendered.append(("hero", *hero(data)))
    rendered.append(("graph", *graph(stats)))
    rendered.append(("chart", *chart(stats)))
    for i, spec in enumerate(TILES):
        rendered.append((spec["file"], *tile(spec, i)))''',
))

# 9. cascade spacing
PAIRS.append((
    '''    rendered.append(("graph", *graph(stats)))

    written = []
    for index, (name, w, h, body, label) in enumerate(rendered):
        offset = index * 0.1''',
    '''
    written = []
    for index, (name, w, h, body, label) in enumerate(rendered):
        offset = index * 0.12''',
))

# 10. preview page: keep the tiles in a row wherever they land in the stack
PAIRS.append((
    '''    hero_file = entries[0][0]
    tiles = entries[1:4]
    rest = entries[4:]
    tile_html = "".join(
        f'<a href="#"><img src="cards/{name}" width="32.5%" alt="{esc(alt)}"></a>'
        for name, alt in tiles
    )
    rest_html = "".join(
        f'<img src="cards/{name}" width="100%" alt="{esc(alt)}">' for name, alt in rest
    )''',
    '''    rows: list[str] = []
    tile_row: list[str] = []

    def flush_tiles() -> None:
        if tile_row:
            rows.append('<div class="tiles">' + "".join(tile_row) + "</div>")
            tile_row.clear()

    for name, alt in entries:
        if name.startswith("tile-"):
            tile_row.append(
                f'<a href="#"><img src="cards/{name}" width="32.5%" alt="{esc(alt)}"></a>'
            )
        else:
            flush_tiles()
            rows.append(f'<img src="cards/{name}" width="100%" alt="{esc(alt)}">')
    flush_tiles()
    stack_html = "\\n".join(rows)''',
))

# 11. preview page: render the assembled rows
PAIRS.append((
    '''<div class="stack">
<img src="cards/{hero_file}" width="100%" alt="hero">
<div class="tiles">{tile_html}</div>
{rest_html}
</div></div></body></html>''',
    '''<div class="stack">
{stack_html}
</div></div></body></html>''',
))


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    before = len(text.encode("utf-8"))
    for i, (old, new) in enumerate(PAIRS, 1):
        found = text.count(old)
        if found != 1:
            sys.exit(f"hunk {i}: expected exactly 1 match, found {found}")
        text = text.replace(old, new, 1)
    TARGET.write_text(text, encoding="utf-8")
    print(f"patched render.py: {before} -> {len(text.encode('utf-8'))} bytes "
          f"({len(PAIRS)} hunks)")


if __name__ == "__main__":
    main()
