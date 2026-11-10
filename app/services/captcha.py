"""Server-side image CAPTCHA: 5 characters, noise, one-time, case-insensitive.

Pure Python: the PNG is drawn with a tiny bitmap font and encoded with zlib,
so the project needs no image library. The answer lives only in the server
session; the browser receives pixels, not text.
"""

import hmac
import io
import secrets
import struct
import zlib
from datetime import timedelta

from flask import session

from app.services.activity import now_utc

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CAPTCHA_LENGTH = 5
CAPTCHA_TTL_MINUTES = 10

_FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".####"),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
}

WIDTH, HEIGHT = 180, 64
SCALE = 4


def _blank():
    return [bytearray([247, 249, 252] * WIDTH) for _ in range(HEIGHT)]


def _dot(pixels, x, y, colour):
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        index = x * 3
        pixels[y][index:index + 3] = bytes(colour)


def _line(pixels, x0, y0, x1, y1, colour):
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    error = dx + dy
    while True:
        _dot(pixels, x0, y0, colour)
        if x0 == x1 and y0 == y1:
            break
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x0 += sx
        if doubled <= dx:
            error += dx
            y0 += sy


def _png(pixels) -> bytes:
    raw = b"".join(b"\x00" + bytes(row) for row in pixels)

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def new_captcha() -> bytes:
    code = "".join(secrets.choice(ALPHABET) for _ in range(CAPTCHA_LENGTH))
    session["captcha_answer"] = code
    session["captcha_at"] = now_utc().isoformat()

    pixels = _blank()
    for _ in range(9):
        colour = (150 + secrets.randbelow(80), 150 + secrets.randbelow(80), 150 + secrets.randbelow(80))
        _line(pixels, secrets.randbelow(WIDTH), secrets.randbelow(HEIGHT),
              secrets.randbelow(WIDTH), secrets.randbelow(HEIGHT), colour)
    for _ in range(160):
        _dot(pixels, secrets.randbelow(WIDTH), secrets.randbelow(HEIGHT),
             (120, 130, 150))

    x = 12
    for char in code:
        glyph = _FONT[char]
        top = 12 + secrets.randbelow(10)
        colour = (20 + secrets.randbelow(80), 20 + secrets.randbelow(80), 20 + secrets.randbelow(80))
        for row, bits in enumerate(glyph):
            for column, bit in enumerate(bits):
                if bit == "#":
                    for dy in range(SCALE):
                        for dx in range(SCALE):
                            _dot(pixels, x + column * SCALE + dx, top + row * SCALE + dy, colour)
        x += 5 * SCALE + 5

    # One line through the text makes segmentation harder without hiding it.
    _line(pixels, 4, 18 + secrets.randbelow(24), WIDTH - 4, 18 + secrets.randbelow(24), (90, 110, 100))
    return _png(pixels)


def check_captcha(answer: str) -> bool:
    expected = session.pop("captcha_answer", None)
    created = session.pop("captcha_at", None)
    if not expected or not created:
        return False
    try:
        started = now_utc().fromisoformat(created)
        if started.tzinfo is None:
            started = started.replace(tzinfo=now_utc().tzinfo)
    except (TypeError, ValueError):
        return False
    if now_utc() - started > timedelta(minutes=CAPTCHA_TTL_MINUTES):
        return False
    return hmac.compare_digest(str(expected).upper(), str(answer or "").strip().upper())
