"""Render the orb to PNG icons using only the stdlib.

Samples the exact radial-gradient stops from index.html so the home-screen
icon matches the page. 3x supersampling for antialiasing, plus a cheap
separable box blur screened back over the top to reproduce the CSS bloom.
"""
import zlib, struct, math

BG = (0x05, 0x0b, 0x1a)

# (radius fraction, #rrggbb) -- lifted straight from the .rings gradient
STOPS = [
    (0.000, "0a1830"), (0.240, "0a1830"),
    (0.265, "dff2ff"), (0.300, "ffffff"), (0.345, "c6e7ff"),
    (0.375, "0b1c3a"), (0.460, "091830"),
    (0.495, "b6e2ff"), (0.550, "ffffff"), (0.605, "d2eeff"),
    (0.640, "2159a4"), (0.700, "17418a"),
    (0.740, "123671"), (0.840, "17458a"),
    (0.905, "0c2450"), (1.000, "050b1a"),
]
STOPS = [(p, tuple(int(h[i:i+2], 16) for i in (0, 2, 4))) for p, h in STOPS]


def sample(t):
    if t <= STOPS[0][0]:
        return STOPS[0][1]
    if t >= STOPS[-1][0]:
        return None                      # outside the disc
    for i in range(len(STOPS) - 1):
        p0, c0 = STOPS[i]
        p1, c1 = STOPS[i + 1]
        if p0 <= t <= p1:
            f = 0 if p1 == p0 else (t - p0) / (p1 - p0)
            return tuple(round(c0[j] + (c1[j] - c0[j]) * f) for j in range(3))
    return None


def blur(buf, w, h, r):
    """Separable box blur, two passes -> roughly gaussian."""
    for _ in range(2):
        out = bytearray(len(buf))
        for y in range(h):                       # horizontal
            row = y * w * 3
            for c in range(3):
                acc = 0
                for x in range(-r, r + 1):
                    acc += buf[row + min(max(x, 0), w - 1) * 3 + c]
                n = 2 * r + 1
                for x in range(w):
                    out[row + x * 3 + c] = acc // n
                    lo = min(max(x - r, 0), w - 1)
                    hi = min(max(x + r + 1, 0), w - 1)
                    acc += buf[row + hi * 3 + c] - buf[row + lo * 3 + c]
        buf2 = bytearray(len(buf))
        for x in range(w):                       # vertical
            for c in range(3):
                acc = 0
                for y in range(-r, r + 1):
                    acc += out[min(max(y, 0), h - 1) * w * 3 + x * 3 + c]
                n = 2 * r + 1
                for y in range(h):
                    buf2[y * w * 3 + x * 3 + c] = acc // n
                    lo = min(max(y - r, 0), h - 1)
                    hi = min(max(y + r + 1, 0), h - 1)
                    acc += out[hi * w * 3 + x * 3 + c] - out[lo * w * 3 + x * 3 + c]
        buf = buf2
    return buf


def render(size):
    ss = 3
    W = size * ss
    buf = bytearray(W * W * 3)
    cx = cy = W / 2.0
    # orb occupies 86% of the tile, leaving room for the halo to fall off
    R = W * 0.43

    for y in range(W):
        for x in range(W):
            dx, dy = (x + 0.5) - cx, (y + 0.5) - cy
            d = math.hypot(dx, dy) / R
            col = sample(d) if d < 1.0 else None
            if col is None:
                # outside the disc: soft blue halo decaying into the background
                g = max(0.0, 1.0 - (d - 1.0) / 0.24) ** 2 if d < 1.24 else 0.0
                g *= 0.55
                col = (round(BG[0] + (0x1e - BG[0]) * g),
                       round(BG[1] + (0x4a - BG[1]) * g),
                       round(BG[2] + (0x8c - BG[2]) * g))
            elif 0.63 < d < 0.95:
                # angular facets across the outer band, as in .facets
                ang = math.degrees(math.atan2(dy, dx)) % 45.0
                f = 1.07 if ang < 11.0 else 0.93
                col = tuple(min(255, round(v * f)) for v in col)
            i = (y * W + x) * 3
            buf[i], buf[i + 1], buf[i + 2] = col

    # the bright pip, offset like the .pip element
    # kept inside the dark core (which ends at 0.24R) so it reads as a distinct
    # dot rather than a crescent bleeding into the inner ring
    px, py = cx + R * 0.085, cy + R * 0.125
    pr = R * 0.10
    for y in range(int(py - pr * 2), int(py + pr * 2) + 1):
        for x in range(int(px - pr * 2), int(px + pr * 2) + 1):
            if not (0 <= x < W and 0 <= y < W):
                continue
            d = math.hypot(x + 0.5 - px, y + 0.5 - py) / pr
            if d > 1.6:
                continue
            a = 1.0 if d <= 1.0 else max(0.0, (1.6 - d) / 0.6) ** 2 * 0.55
            i = (y * W + x) * 3
            for c, v in enumerate((255, 252, 255)):
                buf[i + c] = round(buf[i + c] + (v - buf[i + c]) * a)

    # bloom: blurred copy screened back over the original. Keep this restrained
    # -- too much and the dark navy gaps between the rings disappear, which is
    # exactly what gives the orb its depth.
    bl = blur(bytes(buf), W, W, max(2, W // 150))
    for i in range(len(buf)):
        b, o = bl[i], buf[i]
        buf[i] = 255 - ((255 - o) * (255 - b * 26 // 100)) // 255

    # downsample the supersampled buffer
    out = bytearray(size * size * 3)
    n = ss * ss
    for y in range(size):
        for x in range(size):
            for c in range(3):
                acc = 0
                for sy in range(ss):
                    for sx in range(ss):
                        acc += buf[((y * ss + sy) * W + (x * ss + sx)) * 3 + c]
                out[(y * size + x) * 3 + c] = acc // n
    return out


def write_png(path, size, rgb):
    raw = b"".join(b"\x00" + bytes(rgb[y * size * 3:(y + 1) * size * 3])
                   for y in range(size))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


if __name__ == "__main__":
    import sys
    out = sys.argv[1]
    for name, size in (("apple-touch-icon.png", 180),
                       ("icon-192.png", 192),
                       ("icon-512.png", 512)):
        write_png(f"{out}/{name}", size, render(size))
        print("wrote", name, size)
