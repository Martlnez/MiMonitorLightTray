"""Generate the tray icon as an in-memory PIL image so the package ships no binary assets."""

from __future__ import annotations

from PIL import Image, ImageDraw


def make_tray_icon(size: int = 64, on: bool = True) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    bar_color = (240, 240, 240, 255) if on else (110, 110, 110, 255)
    glow_color = (255, 220, 130, 255) if on else (90, 90, 90, 255)

    bar_top = int(size * 0.15)
    bar_bottom = int(size * 0.30)
    bar_left = int(size * 0.10)
    bar_right = int(size * 0.90)
    d.rounded_rectangle(
        [bar_left, bar_top, bar_right, bar_bottom],
        radius=int(size * 0.05),
        fill=bar_color,
    )

    if on:
        glow_pad = int(size * 0.04)
        for i in range(6):
            alpha = max(0, 110 - i * 18)
            d.polygon(
                [
                    (bar_left + glow_pad - i, bar_bottom),
                    (bar_right - glow_pad + i, bar_bottom),
                    (int(size * 0.80) + i, int(size * 0.95)),
                    (int(size * 0.20) - i, int(size * 0.95)),
                ],
                fill=(255, 220, 130, alpha),
            )
    else:
        d.polygon(
            [
                (bar_left + 4, bar_bottom),
                (bar_right - 4, bar_bottom),
                (int(size * 0.80), int(size * 0.95)),
                (int(size * 0.20), int(size * 0.95)),
            ],
            outline=glow_color,
        )

    stand_w = max(1, int(size * 0.06))
    stand_h = max(2, int(size * 0.10))
    stand_top = max(1, bar_top - stand_h)
    d.rectangle(
        [size // 2 - stand_w, stand_top, size // 2 + stand_w, bar_top],
        fill=bar_color,
    )
    foot_h = max(2, stand_w)
    foot_top = max(0, stand_top - foot_h)
    d.ellipse(
        [size // 2 - stand_w * 2, foot_top, size // 2 + stand_w * 2, stand_top],
        fill=bar_color,
    )

    return img
