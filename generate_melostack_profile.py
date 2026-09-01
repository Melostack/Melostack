from __future__ import annotations

import random
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ROOT = Path('/home/ghostwind/Melostack')
ASSET = ROOT / 'assets'
AVATAR_URL = 'https://avatars.githubusercontent.com/u/229196278?v=4'
AVATAR_PATH = ASSET / 'avatar.jpg'

BG = '#0A101F'
CYAN = '#22D3EE'
CYAN_LIGHT = '#0891B2'
PURPLE = '#A78BFA'
PURPLE_LIGHT = '#7C3AED'
GREEN = '#10B981'
SLATE = '#94A3B8'
WHITE = '#F8FAFC'


def download_avatar() -> None:
    ASSET.mkdir(parents=True, exist_ok=True)
    if not AVATAR_PATH.exists():
        urllib.request.urlretrieve(AVATAR_URL, AVATAR_PATH)


def crop_portrait(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im).convert('RGB')
    w, h = im.size
    # Head-and-shoulders crop, biased slightly upward for a profile avatar.
    side = min(w, h)
    left = max(0, (w - side) // 2)
    top = max(0, (h - side) // 3)
    crop = im.crop((left, top, left + side, top + side))
    return crop.resize((110, 125), Image.Resampling.LANCZOS)


def background_mask(im: Image.Image) -> list[list[bool]]:
    pix = im.load()
    w, h = im.size
    samples = [pix[0, 0], pix[w - 1, 0], pix[0, h - 1], pix[w - 1, h - 1]]
    bg = tuple(sum(s[i] for s in samples) // len(samples) for i in range(3))
    mask: list[list[bool]] = []
    for y in range(h):
        row = []
        for x in range(w):
            p = pix[x, y]
            dist = sum((p[i] - bg[i]) ** 2 for i in range(3)) ** 0.5
            row.append(dist > 34)
        mask.append(row)
    return mask


def dither(im: Image.Image, dark: bool) -> list[tuple[int, int, float]]:
    gray = ImageOps.grayscale(im)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.3)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=3, percent=140, threshold=2))
    w, h = gray.size
    values = [[float(gray.getpixel((x, y))) for x in range(w)] for y in range(h)]
    subject = background_mask(im) if dark else [[True] * w for _ in range(h)]
    points: list[tuple[int, int, float]] = []
    for y in range(h):
        xs = range(w) if y % 2 == 0 else range(w - 1, -1, -1)
        for x in xs:
            if not subject[y][x]:
                values[y][x] = 255.0
                continue
            old = values[y][x]
            new = 0.0 if old < 128 else 255.0
            err = old - new
            # Serpentine Floyd-Steinberg diffusion.
            direction = 1 if y % 2 == 0 else -1
            nx = x + direction
            if 0 <= nx < w:
                values[y][nx] += err * 7 / 16
            if y + 1 < h:
                values[y + 1][x] += err * 5 / 16
                nx2 = x - direction
                if 0 <= nx2 < w:
                    values[y + 1][nx2] += err * 3 / 16
                if 0 <= nx < w:
                    values[y + 1][nx] += err * 1 / 16
            if new == 0.0:
                points.append((x, y, 1.0))
    return points


def dot_paths(points: list[tuple[int, int, float]], ox: int, oy: int, sx: float, sy: float, color: str) -> str:
    # Crisp one-pixel-ish runs, represented as SVG paths rather than font glyphs.
    # Pack all dots in one path element to keep the animated SVG practical.
    commands = []
    for x, y, _ in points:
        commands.append(f'M{ox + x*sx:.1f} {oy + y*sy:.1f}h{max(1.2, sx*0.72):.1f}')
    return f'<path d="{"".join(commands)}" stroke="{color}" stroke-width="{max(1.25, sy*0.72):.1f}" stroke-linecap="square"/>'


def portrait_layer(points: list[tuple[int, int, float]], color: str, prefix: str) -> str:
    rng = random.Random(229196278)
    groups = [[] for _ in range(60)]
    shuffled = points[:]
    rng.shuffle(shuffled)
    for i, p in enumerate(shuffled):
        groups[i % len(groups)].append(p)
    out = []
    for i, group in enumerate(groups):
        body = dot_paths(group, 70, 76, 3.65, 2.95, color)
        begin = 0.15 + (i % 17) * 0.035
        out.append(f'<g id="{prefix}-intro-{i}" opacity="0"><animate attributeName="opacity" values="0;1;1" keyTimes="0;{begin:.3f};1" dur="3.2s" begin="0s" fill="freeze" repeatCount="1"/></g>')
        # The actual dots are duplicated for the intro and loop layer.
        out.append(f'<g id="{prefix}-dots-{i}">{body}</g>')
    return ''.join(out)


def bitcoin_icon(cx: float, cy: float, r: float, color: str, variant: int) -> str:
    if variant == 0:
        return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="3"/><path d="M{cx-5} {cy-r+8}v{2*r-16}M{cx+2} {cy-r+8}v{2*r-16}M{cx-8} {cy-6}h13c8 0 8 12 0 12H{cx-8}c10 0 12-12 2-12" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    if variant == 1:
        return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" opacity=".14" stroke="{color}" stroke-width="3"/><path d="M{cx-3} {cy-r+7}v{2*r-14}M{cx+4} {cy-r+7}v{2*r-14}M{cx-8} {cy-7}h13c8 0 8 12 0 12H{cx-8}c10 0 12-12 2-12" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round"/>'
    return f'<path d="M{cx} {cy-r}l{r*.72} {r*.42}v{r*.9}c0 {r*.8}-{r*.72} {r*1.1}-{r*.72} {r*1.1}s-{r*.72}-{r*.72}-{r*1.1}v-{r*.9}z" fill="none" stroke="{color}" stroke-width="3"/><path d="M{cx-4} {cy-r+9}v{r*1.55}M{cx+3} {cy-r+9}v{r*1.55}M{cx-8} {cy-5}h12c7 0 7 10 0 10H{cx-8}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round"/>'


def banner(dark: bool) -> str:
    im = crop_portrait(Image.open(AVATAR_PATH))
    pts = dither(im, dark)
    accent = PURPLE if dark else PURPLE_LIGHT
    chrome = CYAN if dark else CYAN_LIGHT
    # Use a stable subset for a practical SVG size while retaining dense detail.
    portrait = pts[::1]
    pbody = dot_paths(portrait, 70, 76, 3.65, 2.95, accent)
    groups = []
    rng = random.Random(42)
    shuffled = portrait[:]
    rng.shuffle(shuffled)
    for i in range(60):
        part = shuffled[i::60]
        groups.append(f'<g opacity="0"><animate attributeName="opacity" values="0;1;1" keyTimes="0;{0.18 + (i % 11)*0.045:.3f};1" dur="3.2s" begin="0s" fill="freeze" repeatCount="1"/>{dot_paths(part, 70, 76, 3.65, 2.95, accent)}</g>')
    groups_text = ''.join(groups)
    logo_frames = ''.join(f'<g opacity="0"><animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;0.23;0.28;0.39;0.47" dur="14.2s" repeatCount="indefinite" begin="-{i*0.15}s"/>{bitcoin_icon(520, 245, 42, [chrome, GREEN, accent][i], i)}</g>' for i in range(3))
    lines = [
        ('Subject', 'Melo.x'), ('Role', 'Web3, Bitcoin & AI Builder'), ('Origin', 'Bitcoin / Blockchain'),
        ('Status', 'Building + Learning + Shipping'), ('ToolChain', 'Codex · Claude · Grok · Cursor · Hermes'),
        ('Core.Lang', 'Bitcoin · Blockchain · AI'), ('Core.Frontend', 'Automation · Interfaces'),
        ('Core.Backend', 'Agents · APIs · Systems'), ('Core.Database', 'Data · Memory · Signals'),
        ('Core.Infra', 'Oratech · Vercel · GitHub'), ('Grid.Mail', 'contato@oratechsolutions.com.br'),
        ('Grid.GitHub', 'github.com/Melostack'),
    ]
    rows = []
    for i, (label, value) in enumerate(lines):
        y = 104 + i * 28
        rows.append(f'<text x="535" y="{y}" fill="{SLATE}" font-size="14" textLength="115" lengthAdjust="spacingAndGlyphs">{escape(label)}</text><text x="665" y="{y}" fill="{WHITE}" font-size="14" textLength="430" lengthAdjust="spacingAndGlyphs">{escape(value)}</text><path d="M655 {y-4}h-10" stroke="{chrome}" stroke-dasharray="2 5" opacity=".65"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="610" viewBox="0 0 1180 610" role="img" aria-labelledby="title desc">
<title id="title">Melo.x — profile.sh --live</title><desc id="desc">Animated Bitcoin, blockchain and AI profile for Melo.x.</desc>
<rect width="1180" height="610" rx="18" fill="{BG}"/><rect x="1" y="1" width="1178" height="608" rx="17" fill="none" stroke="{chrome}" stroke-opacity=".45"/>
<rect x="1" y="1" width="1178" height="42" rx="17" fill="{chrome}" fill-opacity=".08"/><circle cx="25" cy="22" r="6" fill="#F87171"/><circle cx="45" cy="22" r="6" fill="#FBBF24"/><circle cx="65" cy="22" r="6" fill="{GREEN}"/><text x="92" y="27" fill="{SLATE}" font-size="14" font-family="monospace">profile.sh --live</text><rect x="1045" y="10" width="94" height="24" rx="12" fill="#EF4444" fill-opacity=".18" stroke="#EF4444"/><circle cx="1060" cy="22" r="4" fill="#EF4444"><animate attributeName="opacity" values="1;.25;1" dur="1.2s" repeatCount="indefinite"/></circle><text x="1072" y="27" fill="#FCA5A5" font-size="12" font-family="monospace">LIVE</text>
<rect x="30" y="63" width="440" height="515" rx="12" fill="#111A2E" stroke="{chrome}" stroke-opacity=".35"/><text x="52" y="91" fill="{chrome}" font-size="12" font-family="monospace">VISUAL.MAP</text><path d="M52 102h396" stroke="{chrome}" stroke-opacity=".25" stroke-dasharray="3 6"/>
<g shape-rendering="crispEdges">{pbody}</g><g shape-rendering="crispEdges">{groups_text}</g>
<rect x="52" y="532" width="200" height="26" rx="13" fill="{accent}" fill-opacity=".16"/><text x="68" y="550" fill="{accent}" font-size="13" font-family="monospace">Melo.x / @Melostack</text>
<text x="520" y="72" fill="{chrome}" font-size="13" font-family="monospace">SYSTEM.INFO</text><path d="M520 84h610" stroke="{chrome}" stroke-opacity=".25" stroke-dasharray="3 6"/>{''.join(rows)}
<g>{logo_frames}</g><text x="480" y="570" fill="{SLATE}" opacity=".7" font-size="11" font-family="monospace">Bitcoin is the signal. Systems are the medium.</text>
</svg>'''


def main() -> None:
    download_avatar()
    (ROOT / 'dark.svg').write_text(banner(True), encoding='utf-8')
    (ROOT / 'light.svg').write_text(banner(False), encoding='utf-8')
    print('generated', ROOT / 'dark.svg', ROOT / 'light.svg')


if __name__ == '__main__':
    main()
