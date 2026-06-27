"""Generate the tray icon as an in-memory PIL image with Windows 11 Fluent Design style."""

from __future__ import annotations

from PIL import Image, ImageDraw


def make_tray_icon(size: int = 64, on: bool = True) -> Image.Image:
    """Create a modern, minimalist tray icon inspired by Windows 11 Fluent Design.

    Design: A sleek monitor light bar with subtle rounded corners and a soft glow
    when on, or a simple outline when off.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Color palette - Windows 11 inspired
    if on:
        bar_color = (255, 255, 255, 255)  # Pure white bar
        glow_primary = (255, 185, 0, 180)  # Warm amber glow
        glow_secondary = (255, 220, 100, 120)
        accent = (255, 200, 50, 200)
    else:
        bar_color = (160, 160, 160, 255)  # Neutral gray
        glow_primary = (120, 120, 120, 80)
        glow_secondary = None
        accent = (140, 140, 140, 180)

    # Main light bar - sleek horizontal bar with rounded ends
    bar_top = int(size * 0.28)
    bar_bottom = int(size * 0.42)
    bar_left = int(size * 0.12)
    bar_right = int(size * 0.88)
    bar_radius = int(size * 0.07)

    # Glow effect when on - soft layered gradient
    if on:
        # Outer glow
        for i in range(4):
            alpha_factor = (4 - i) / 4.0
            glow_y_offset = int(size * 0.03 * i)
            d.rounded_rectangle(
                [
                    bar_left - i * 2,
                    bar_bottom,
                    bar_right + i * 2,
                    bar_bottom + int(size * 0.48) + glow_y_offset,
                ],
                radius=bar_radius + i * 2,
                fill=(
                    glow_secondary[0] if glow_secondary else glow_primary[0],
                    glow_secondary[1] if glow_secondary else glow_primary[1],
                    glow_secondary[2] if glow_secondary else glow_primary[2],
                    int((glow_secondary[3] if glow_secondary else glow_primary[3]) * alpha_factor * 0.4),
                ),
            )

        # Core glow
        d.rounded_rectangle(
            [bar_left, bar_bottom, bar_right, bar_bottom + int(size * 0.38)],
            radius=bar_radius,
            fill=glow_primary,
        )

    # Main light bar body
    d.rounded_rectangle(
        [bar_left, bar_top, bar_right, bar_bottom],
        radius=bar_radius,
        fill=bar_color,
    )

    # Accent LED indicators on bar (small dots)
    led_y = (bar_top + bar_bottom) // 2
    led_radius = max(1, int(size * 0.025))
    led_spacing = (bar_right - bar_left) // 4

    for i in range(3):
        led_x = bar_left + led_spacing * (i + 1)
        d.ellipse(
            [led_x - led_radius, led_y - led_radius, led_x + led_radius, led_y + led_radius],
            fill=accent,
        )

    # Minimal mount bracket - thin vertical line
    bracket_w = max(1, int(size * 0.015))
    bracket_h = int(size * 0.12)
    bracket_top = max(1, bar_top - bracket_h)
    bracket_x = size // 2

    d.rectangle(
        [bracket_x - bracket_w, bracket_top, bracket_x + bracket_w, bar_top],
        fill=bar_color,
    )

    # Subtle top connector
    connector_radius = int(size * 0.04)
    d.ellipse(
        [
            bracket_x - connector_radius,
            bracket_top - connector_radius // 2,
            bracket_x + connector_radius,
            bracket_top + connector_radius // 2,
        ],
        fill=(bar_color[0], bar_color[1], bar_color[2], int(bar_color[3] * 0.7)),
    )

    return img
