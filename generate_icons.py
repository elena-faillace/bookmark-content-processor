"""Generate a glossy game-style golden star icon for browser extensions."""
import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def star_points(cx, cy, outer_r, inner_r, n=5):
    pts = []
    for i in range(2 * n):
        angle = math.radians(-90 + i * 180 / n)
        r = outer_r if i % 2 == 0 else inner_r
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts


def apply_mask(img: Image.Image, mask: Image.Image) -> Image.Image:
    """Multiply img alpha by mask. Uses float32 to avoid uint8 overflow."""
    a = np.array(img, dtype=np.float32)
    m = np.array(mask, dtype=np.float32) / 255.0
    a[:, :, 3] *= m
    return Image.fromarray(a.astype(np.uint8))


def gradient_image(size, top_rgb, bot_rgb):
    """Vertical gradient, fully opaque."""
    t = np.linspace(0, 1, size, dtype=np.float32)[:, None]   # (H, 1)
    top = np.array(top_rgb, dtype=np.float32)
    bot = np.array(bot_rgb, dtype=np.float32)
    rgb = top * (1 - t) + bot * t                             # (H, 3)
    rgb = np.tile(rgb[:, None, :], (1, size, 1))              # (H, W, 3)
    alpha = np.full((size, size, 1), 255, dtype=np.float32)
    return Image.fromarray(np.concatenate([rgb, alpha], axis=2).astype(np.uint8))


def star_mask(size, cx, cy, outer_r, inner_r, blur=0):
    """Star-shaped L mask, optionally smoothed."""
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).polygon(star_points(cx, cy, outer_r, inner_r), fill=255)
    if blur:
        m = m.filter(ImageFilter.GaussianBlur(radius=blur))
    return m


def make_star_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    cx, cy = size * 0.50, size * 0.50
    R = size * 0.43          # outer tip radius of the fill star
    r = R * 0.415            # inner concave radius

    # border star is a bit larger
    Rb = R + size * 0.05
    rb = Rb * 0.415

    # ── 1. Rainbow glow (behind everything) ──────────────────────────────────
    # Each pixel outside the border star is colored by its angle from the
    # centre (full hue wheel), so the glow traces the star edge in rainbow.
    Y, X = np.mgrid[0:size, 0:size].astype(np.float32)
    angle = np.arctan2(Y - cy, X - cx)               # -π … π
    hue = ((angle / (2 * np.pi) + 0.5) * 360) % 360  # 0 … 360

    # Vectorised HSV→RGB (S=1, V=1)
    h6 = hue / 60.0
    hi = h6.astype(np.int32) % 6
    f  = h6 - np.floor(h6)
    q  = 1 - f
    rgb_table = np.stack([
        np.ones_like(f), q,               np.zeros_like(f),
        f,               np.ones_like(f), np.zeros_like(f),
        np.zeros_like(f),np.ones_like(f), q,
        np.zeros_like(f),f,               np.ones_like(f),
        q,               np.zeros_like(f),np.ones_like(f),
        np.ones_like(f), np.zeros_like(f),f,
    ], axis=0).reshape(6, 3, size, size)
    ch_r = rgb_table[hi, 0, Y.astype(int), X.astype(int)]
    ch_g = rgb_table[hi, 1, Y.astype(int), X.astype(int)]
    ch_b = rgb_table[hi, 2, Y.astype(int), X.astype(int)]

    # Glow mask: bright just outside the border star, fades outward
    glow_w = max(2, size * 0.10)
    border_m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(border_m).polygon(star_points(cx, cy, Rb, rb), fill=255)
    outer_m = border_m.filter(ImageFilter.GaussianBlur(radius=glow_w))
    outer_arr  = np.array(outer_m,  dtype=np.float32) / 255.0
    border_arr = np.array(border_m, dtype=np.float32) / 255.0
    glow_alpha = np.clip(outer_arr - border_arr, 0, 1)   # ring outside the star
    glow_alpha = (glow_alpha / max(glow_alpha.max(), 1e-6) * 210).astype(np.uint8)

    glow_arr = np.stack([
        (ch_r * 255).astype(np.uint8),
        (ch_g * 255).astype(np.uint8),
        (ch_b * 255).astype(np.uint8),
        glow_alpha,
    ], axis=2)
    img = Image.alpha_composite(img, Image.fromarray(glow_arr))

    # ── 2. Drop shadow (soft, offset down-right) ─────────────────────────────
    shad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    off = size * 0.025
    ImageDraw.Draw(shad).polygon(
        star_points(cx + off, cy + off, Rb, rb), fill=(20, 5, 0, 160))
    shad = shad.filter(ImageFilter.GaussianBlur(radius=max(1, size * 0.07)))
    img = Image.alpha_composite(img, shad)

    # ── 3. Dark brown border star ─────────────────────────────────────────────
    border_lyr = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(border_lyr).polygon(
        star_points(cx, cy, Rb, rb), fill=(70, 28, 4, 255))
    img = Image.alpha_composite(img, border_lyr)

    # ── 4. Gold fill: vivid bright yellow top → warm amber bottom ────────────
    fill_m = star_mask(size, cx, cy, R, r)
    gold = gradient_image(size, top_rgb=(255, 235, 30), bot_rgb=(225, 120, 5))
    img = Image.alpha_composite(img, apply_mask(gold, fill_m))

    # ── 5. Lower shadow overlay (bottom 45% of star, clipped) ────────────────
    rows = np.arange(size, dtype=np.float32)
    lo_arr = np.zeros((size, size, 4), dtype=np.float32)
    lo_alpha = np.clip((rows - (cy + R * 0.0)) / (R * 0.60), 0, 1) ** 1.3 * 110
    lo_arr[:, :, :3] = [175, 75, 0]
    lo_arr[:, :, 3] = lo_alpha[:, None]
    img = Image.alpha_composite(img, apply_mask(Image.fromarray(lo_arr.astype(np.uint8)), fill_m))

    # ── 6. Glossy highlight clipped inside the star ───────────────────────────
    # Draw highlight on a separate layer, then mask to star shape
    hl = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(hl)

    # Position: just below the top tip, slightly left of centre
    h_cx = cx - R * 0.08
    h_cy = cy - R * 0.50
    hw = R * 0.32
    hh = R * 0.09

    # Soft glow halo
    hdraw.ellipse([h_cx - hw * 1.7, h_cy - hh * 2.2,
                   h_cx + hw * 1.7, h_cy + hh * 2.2],
                  fill=(255, 255, 230, 30))
    # Main highlight body
    hdraw.ellipse([h_cx - hw, h_cy - hh, h_cx + hw, h_cy + hh],
                  fill=(255, 255, 235, 205))
    # Pure white core
    hdraw.ellipse([h_cx - hw * 0.52, h_cy - hh * 0.65,
                   h_cx + hw * 0.52, h_cy + hh * 0.65],
                  fill=(255, 255, 255, 255))

    img = Image.alpha_composite(img, apply_mask(hl, fill_m))

    return img


def save_icons(sizes, out_dirs):
    for d in out_dirs:
        icons_dir = os.path.join(d, "icons")
        os.makedirs(icons_dir, exist_ok=True)
        for sz in sizes:
            img = make_star_icon(sz)
            path = os.path.join(icons_dir, f"icon{sz}.png")
            img.save(path)
            print(f"Saved {path}")


if __name__ == "__main__":
    save_icons([16, 48, 128], ["extension-chrome", "extension-firefox"])
    print("Done.")
