"""Generate the tray icon as an in-memory PIL image with Windows 11 line-art style."""

from __future__ import annotations

from PIL import Image, ImageDraw


def make_tray_icon(size: int = 64, on: bool = True) -> Image.Image:
    """Create a Windows 11 style line-art tray icon for a monitor light bar.

    Design: Minimalist line-drawn monitor with a light bar on top, inspired by
    Windows 11 Settings icons (pure lines, no fills, adaptive to system theme).

    The icon uses a single solid color that works in both light and dark themes:
    - ON:  White (#FFFFFF) - high contrast, visible on dark taskbar
    - OFF: Gray (#888888) - muted, indicates inactive state
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Color scheme - Win11 line-art style (single color, no gradients)
    line_color = (255, 255, 255, 255) if on else (136, 136, 136, 255)
    line_width = max(2, int(size * 0.04))  # Thicker lines for better visibility at small sizes

    # Center the drawing
    center_x = size // 2
    center_y = size // 2

    # Light bar dimensions (top horizontal bar)
    bar_width = int(size * 0.55)
    bar_height = int(size * 0.08)
    bar_left = center_x - bar_width // 2
    bar_right = center_x + bar_width // 2
    bar_top = int(size * 0.22)
    bar_bottom = bar_top + bar_height

    # Light bar - filled rectangle with rounded corners when ON
    if on:
        # Filled bar with slight rounding
        d.rounded_rectangle(
            [bar_left, bar_top, bar_right, bar_bottom],
            radius=int(size * 0.04),
            fill=line_color,
        )
    else:
        # Outline only when OFF
        d.rounded_rectangle(
            [bar_left, bar_top, bar_right, bar_bottom],
            radius=int(size * 0.04),
            outline=line_color,
            width=line_width,
        )

    # Monitor screen - rounded rectangle outline
    screen_width = int(size * 0.50)
    screen_height = int(size * 0.32)
    screen_left = center_x - screen_width // 2
    screen_right = center_x + screen_width // 2
    screen_top = int(size * 0.38)
    screen_bottom = screen_top + screen_height

    d.rounded_rectangle(
        [screen_left, screen_top, screen_right, screen_bottom],
        radius=int(size * 0.03),
        outline=line_color,
        width=line_width,
    )

    # Monitor stand - simple vertical line + base
    stand_top = screen_bottom
    stand_bottom = int(size * 0.80)
    stand_x = center_x

    d.line(
        [(stand_x, stand_top), (stand_x, stand_bottom)],
        fill=line_color,
        width=line_width,
    )

    # Monitor base - horizontal line
    base_width = int(size * 0.25)
    base_y = stand_bottom
    d.line(
        [(center_x - base_width // 2, base_y), (center_x + base_width // 2, base_y)],
        fill=line_color,
        width=line_width,
    )

    # Glow indicator when ON - small circle/dot above the bar
    if on:
        glow_radius = int(size * 0.04)
        glow_y = bar_top - int(size * 0.08)
        d.ellipse(
            [center_x - glow_radius, glow_y - glow_radius,
             center_x + glow_radius, glow_y + glow_radius],
            fill=line_color,
        )

    return img
