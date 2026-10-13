"""Build STE app icons (PNG + ICO) without extra dependencies."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEAL = (12, 107, 92, 255)
TEAL_DARK = (8, 73, 63, 255)
CREAM = (255, 253, 248, 255)


def _blend(src: tuple[int, int, int, int], dst: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    sa = src[3] / 255
    if sa <= 0:
        return dst
    out_a = src[3] + dst[3] * (1 - sa)
    if out_a <= 0:
        return (0, 0, 0, 0)
    rgb = tuple(int(round((src[i] * src[3] + dst[i] * dst[3] * (1 - sa)) / out_a)) for i in range(3))
    return (rgb[0], rgb[1], rgb[2], int(round(out_a)))


def paint(size: int) -> list[list[tuple[int, int, int, int]]]:
    pixels = [[(0, 0, 0, 0) for _ in range(size)] for _ in range(size)]
    cx = cy = (size - 1) / 2
    outer = size * 0.46
    inner = size * 0.40

    def set_px(x: int, y: int, color: tuple[int, int, int, int]) -> None:
        if 0 <= x < size and 0 <= y < size:
            pixels[y][x] = _blend(color, pixels[y][x])

    for y in range(size):
        for x in range(size):
            dx = x - cx
            dy = y - cy
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= outer:
                t = max(0.0, min(1.0, (dist / outer)))
                color = (
                    int(TEAL[0] * (1 - t) + TEAL_DARK[0] * t),
                    int(TEAL[1] * (1 - t) + TEAL_DARK[1] * t),
                    int(TEAL[2] * (1 - t) + TEAL_DARK[2] * t),
                    255 if dist <= inner else int(255 * max(0.0, (outer - dist) / (outer - inner))),
                )
                set_px(x, y, color)

    drop_cx = cx
    drop_cy = cy + size * 0.04
    drop_r = size * 0.16
    tip_y = drop_cy - size * 0.22
    for y in range(size):
        for x in range(size):
            dx = (x - drop_cx) / drop_r
            dy_ball = (y - drop_cy) / drop_r
            in_ball = dx * dx + dy_ball * dy_ball <= 1
            if y <= drop_cy:
                span = max(0.08, (y - tip_y) / max(1, drop_cy - tip_y))
                in_tip = tip_y <= y <= drop_cy and abs(x - drop_cx) <= drop_r * span
            else:
                in_tip = False
            if in_ball or in_tip:
                set_px(x, y, CREAM)
    return pixels


def png_bytes(pixels: list[list[tuple[int, int, int, int]]]) -> bytes:
    height = len(pixels)
    width = len(pixels[0])
    raw = b"".join(b"\x00" + b"".join(struct.pack("BBBB", *px) for px in row) for row in pixels)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def ico_bytes(pixels: list[list[tuple[int, int, int, int]]]) -> bytes:
    size = len(pixels)
    xor = bytearray()
    for y in range(size - 1, -1, -1):
        for x in range(size):
            r, g, b, a = pixels[y][x]
            xor += struct.pack("BBBB", b, g, r, a)
    row_mask = ((size + 31) // 32) * 4
    mask = bytearray(row_mask * size)
    header = struct.pack("<IIIHHIIIIII", 40, size, size * 2, 1, 32, 0, len(xor), 0, 0, 0, 0)
    image = header + xor + mask
    directory = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0, 0, 0, 1, 32, len(image), 22)
    return directory + entry + image


def write_icons() -> None:
    static = ROOT / "ste" / "static"
    static.mkdir(parents=True, exist_ok=True)
    for size, name in ((192, "icon-192.png"), (512, "icon-512.png")):
        (static / name).write_bytes(png_bytes(paint(size)))
    (ROOT / "ste.ico").write_bytes(ico_bytes(paint(32)))
    print("wrote icons")


if __name__ == "__main__":
    write_icons()
