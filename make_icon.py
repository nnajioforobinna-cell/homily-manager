"""
Homily Manager - generate the app icon (an open Bible).

Draws the icon with Pillow and writes the PNG sizes the web app and a later
desktop wrap need, into static/. Re-runnable:  python make_icon.py
Pillow is only needed to regenerate the icon, not to run the app.
"""

import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(HERE, "static")

S = 4                      # supersample factor for smooth edges
N = 1024                   # logical size
PX = N * S

BG1 = (122, 90, 48)        # warm brown (top)
BG2 = (92, 67, 35)         # warm brown (bottom), for a soft vertical shade
COVER = (74, 54, 28)       # book cover / thickness
COVER_EDGE = (58, 42, 22)
PAGE = (248, 246, 241)     # cream page
PAGE_SHADE = (228, 223, 212)
SPINE = (120, 95, 60)
LINE = (172, 134, 86)      # faint "text" lines
RIBBON = (158, 46, 46)     # deep red bookmark
GOLD = (210, 170, 92)      # cross


def s(p):
    return (p[0] * S, p[1] * S)


def qbez(p0, p1, p2, n=60):
    out = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        out.append((x, y))
    return out


def mirror(pts):
    return [(N - x, y) for (x, y) in pts]


def page(outer_top, top_ctrl, outer_bottom, bottom_ctrl,
         spine_top=(512, 330), spine_bottom=(512, 712)):
    path = []
    path += qbez(spine_top, top_ctrl, outer_top)
    path.append(outer_bottom)
    path += qbez(outer_bottom, bottom_ctrl, spine_bottom)
    return path


def draw():
    img = Image.new("RGB", (PX, PX), BG1)
    d = ImageDraw.Draw(img)

    # soft vertical shade on the background
    for y in range(PX):
        t = y / PX
        c = tuple(int(BG1[i] + (BG2[i] - BG1[i]) * t) for i in range(3))
        d.line([(0, y), (PX, y)], fill=c)

    # drop shadow under the book
    shadow = [s((x, y + 26)) for (x, y) in
              page((112, 432), (300, 300), (150, 706), (330, 760))]
    shadow += [s((x, y + 26)) for (x, y) in
               reversed(mirror(page((112, 432), (300, 300), (150, 706), (330, 760))))]
    sh = Image.new("RGBA", (PX, PX), (0, 0, 0, 0))
    ImageDraw.Draw(sh).polygon(shadow, fill=(0, 0, 0, 70))
    img.paste(Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB"), (0, 0))
    d = ImageDraw.Draw(img)

    # book cover (slightly larger, behind the pages)
    cover_l = page((98, 440), (300, 292), (138, 724), (330, 784),
                   spine_bottom=(512, 730))
    cover = [s(p) for p in cover_l] + [s(p) for p in reversed(mirror(cover_l))]
    d.polygon(cover, fill=COVER, outline=COVER_EDGE, width=2 * S)

    # the two open pages
    left = page((112, 432), (300, 300), (150, 706), (330, 760))
    right = mirror(left)
    d.polygon([s(p) for p in left], fill=PAGE)
    d.polygon([s(p) for p in right], fill=PAGE)

    # a touch of shade along the spine valley
    d.line([s((512, 330)), s((512, 712))], fill=PAGE_SHADE, width=5 * S)
    d.line([s((512, 334)), s((512, 708))], fill=SPINE, width=2 * S)

    # faint text lines on each page (follow the page angle)
    for i, yoff in enumerate(range(0, 5)):
        y = 470 + yoff * 48
        shrink = yoff * 10
        # left page: from near spine outward
        d.line([s((486, y)), s((205 + shrink, y - 18 - yoff * 6))],
               fill=LINE, width=3 * S)
        # right page (mirror)
        d.line([s((N - 486, y)), s((N - 205 - shrink, y - 18 - yoff * 6))],
               fill=LINE, width=3 * S)

    # ribbon bookmark hanging from the spine
    d.polygon([s((494, 700)), s((530, 700)), s((530, 830)),
               s((512, 806)), s((494, 830))], fill=RIBBON)

    # small gold cross above the open book
    cx, cy = 512, 232
    d.rectangle([s((cx - 9, cy - 56)), s((cx + 9, cy + 44))], fill=GOLD)
    d.rectangle([s((cx - 40, cy - 22)), s((cx + 40, cy - 4))], fill=GOLD)

    return img.resize((N, N), Image.LANCZOS)


def main():
    master = draw()
    os.makedirs(STATIC, exist_ok=True)
    for size, name in [(180, "icon-180.png"), (192, "icon-192.png"),
                       (512, "icon-512.png"), (32, "favicon.png")]:
        master.resize((size, size), Image.LANCZOS).save(
            os.path.join(STATIC, name))
    # a maskable-friendly master too
    master.save(os.path.join(STATIC, "icon-master.png"))
    print("Wrote icons to", STATIC)


if __name__ == "__main__":
    main()
