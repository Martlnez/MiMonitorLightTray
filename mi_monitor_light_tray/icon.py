"""Generate the tray icon as an in-memory PIL image with Windows 11 line-art style."""

from __future__ import annotations

from PIL import Image, ImageDraw


def make_tray_icon(size: int = 64, on: bool = True) -> Image.Image:
    """Create a Windows 11 style line-art tray icon for a monitor light bar.

    Design: Minimalist line-drawn monitor with a light bar on top, optimized
    for small sizes (16x16, 32x32). Uses thicker lines and simpler shapes
    for better clarity at tray icon scale.

    The icon uses a single solid color that works in both light and dark themes:
    - ON:  White (#FFFFFF) - high contrast, visible on dark taskbar
    - OFF: Gray (#888888) - muted, indicates inactive state
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Color scheme - Win11 line-art style
    line_color = (255, 255, 255, 255) if on else (136, 136, 136, 255)

    # Adaptive line width based on size - thicker for small icons
    if size <= 16:
        line_width = 2
    elif size <= 32:
        line_width = 3
    else:
        line_width = max(3, int(size * 0.05))

    # Center the drawing with more padding for better visibility
    center_x = size // 2
    center_y = size // 2
    padding = int(size * 0.08)  # More padding to make icon look larger

    # Light bar dimensions (top horizontal bar) - more prominent
    bar_width = int(size * 0.65)  # Wider for better visibility
    bar_height = max(3, int(size * 0.12))  # Thicker bar
    bar_left = center_x - bar_width // 2
    bar_right = center_x + bar_width // 2
    bar_top = padding + int(size * 0.10)
    bar_bottom = bar_top + bar_height

    # Light bar - always filled for better visibility
    d.rounded_rectangle(
        [bar_left, bar_top, bar_right, bar_bottom],
        radius=max(2, int(size * 0.04)),
        fill=line_color,
    )

    # Monitor screen - simplified rectangle (no rounded corners at small sizes)
    screen_width = int(size * 0.60)
    screen_height = int(size * 0.35)
    screen_left = center_x - screen_width // 2
    screen_right = center_x + screen_width // 2
    screen_top = bar_bottom + int(size * 0.08)
    screen_bottom = screen_top + screen_height

    if size <= 16:
        # Simple rectangle for 16x16
        d.rectangle(
            [screen_left, screen_top, screen_right, screen_bottom],
            outline=line_color,
            width=line_width,
        )
    else:
        d.rounded_rectangle(
            [screen_left, screen_top, screen_right, screen_bottom],
            radius=max(2, int(size * 0.03)),
            outline=line_color,
            width=line_width,
        )

    # Monitor stand - thicker for visibility
    stand_top = screen_bottom
    stand_bottom = size - padding - int(size * 0.08)
    stand_x = center_x
    stand_width = max(line_width, int(size * 0.06))

    d.rectangle(
        [stand_x - stand_width // 2, stand_top, stand_x + stand_width // 2, stand_bottom],
        fill=line_color,
    )

    # Monitor base - wider and thicker
    base_width = int(size * 0.35)
    base_height = max(line_width, int(size * 0.06))
    base_y = stand_bottom

    d.rectangle(
        [center_x - base_width // 2, base_y, center_x + base_width // 2, base_y + base_height],
        fill=line_color,
    )

    # Glow indicator when ON - larger dot for visibility
    if on:
        if size <= 16:
            glow_radius = 2
        elif size <= 32:
            glow_radius = 3
        else:
            glow_radius = max(3, int(size * 0.05))

        glow_y = bar_top - glow_radius - 2
        d.ellipse(
            [center_x - glow_radius, glow_y - glow_radius,
             center_x + glow_radius, glow_y + glow_radius],
            fill=line_color,
        )

    return img
