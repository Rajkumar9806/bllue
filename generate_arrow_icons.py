#!/usr/bin/env python3
"""
Icon Generator for Arrow App
Generates Cupid's Arrow + Heart icon for App Store, Play Store, and web.
Design: A coral-pink heart with a sleek diagonal arrow piercing through it.
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

os.makedirs('frontend/assets/images', exist_ok=True)
os.makedirs('/sessions/jolly-elegant-bohr/mnt/outputs', exist_ok=True)


def create_gradient(size, color1, color2, angle=135):
    """Create a diagonal gradient background."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    rad = math.radians(angle)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    for y in range(size):
        for x in range(size):
            # Project point onto gradient direction
            nx = x / size
            ny = y / size
            t = nx * cos_a + ny * sin_a
            t = max(0, min(1, (t + 0.5) / 1.5))  # normalize
            r = int(color1[0] + (color2[0] - color1[0]) * t)
            g = int(color1[1] + (color2[1] - color1[1]) * t)
            b = int(color1[2] + (color2[2] - color1[2]) * t)
            draw.point((x, y), fill=(r, g, b, 255))

    return img


def create_gradient_fast(size, color1, color2):
    """Create a vertical gradient (fast version for large images)."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for y in range(size):
        ratio = y / size
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    return img


def draw_heart_smooth(img, center_x, center_y, size, color):
    """Draw a smooth, well-proportioned heart shape using parametric equations."""
    draw = ImageDraw.Draw(img)
    scale = size / 2

    # Generate heart points using parametric equation
    points = []
    for i in range(360):
        t = math.radians(i)
        x = 16 * (math.sin(t) ** 3)
        y = -(13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t))

        px = center_x + x * scale / 17
        py = center_y + y * scale / 17
        points.append((px, py))

    draw.polygon(points, fill=color)
    return points


def draw_arrow(draw, x1, y1, x2, y2, thickness, color, head_size):
    """Draw a sleek arrow with arrowhead and tail feathers."""
    angle = math.atan2(y2 - y1, x2 - x1)
    length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    perp_cos = math.cos(angle + math.pi/2)
    perp_sin = math.sin(angle + math.pi/2)

    # Arrow shaft (thick line)
    half_t = thickness / 2
    shaft_points = [
        (x1 + perp_cos * half_t, y1 + perp_sin * half_t),
        (x2 + perp_cos * half_t, y2 + perp_sin * half_t),
        (x2 - perp_cos * half_t, y2 - perp_sin * half_t),
        (x1 - perp_cos * half_t, y1 - perp_sin * half_t),
    ]
    draw.polygon(shaft_points, fill=color)

    # Arrowhead (triangle)
    tip_x = x2 + cos_a * head_size * 0.6
    tip_y = y2 + sin_a * head_size * 0.6
    head_base_x = x2 - cos_a * head_size * 0.3
    head_base_y = y2 - sin_a * head_size * 0.3

    head_width = head_size * 0.5
    head_points = [
        (tip_x, tip_y),
        (head_base_x + perp_cos * head_width, head_base_y + perp_sin * head_width),
        (head_base_x - perp_cos * head_width, head_base_y - perp_sin * head_width),
    ]
    draw.polygon(head_points, fill=color)

    # Tail feathers (small V at the back)
    tail_len = head_size * 0.35
    tail_spread = head_size * 0.25

    for side in [1, -1]:
        feather_points = [
            (x1 - cos_a * 2, y1 - sin_a * 2),
            (x1 - cos_a * tail_len + perp_cos * tail_spread * side,
             y1 - sin_a * tail_len + perp_sin * tail_spread * side),
            (x1 - cos_a * tail_len * 0.7 + perp_cos * tail_spread * 0.3 * side,
             y1 - sin_a * tail_len * 0.7 + perp_sin * tail_spread * 0.3 * side),
        ]
        draw.polygon(feather_points, fill=color)


def create_arrow_icon(size, output_path, include_background=True):
    """Create the main Arrow app icon: heart with Cupid's arrow through it."""
    # Use supersampling for anti-aliasing
    ss = 4  # supersample factor
    ss_size = size * ss

    img = Image.new('RGBA', (ss_size, ss_size), (0, 0, 0, 0))

    if include_background:
        # Rich coral-to-rose gradient
        gradient = create_gradient_fast(ss_size, (232, 56, 88), (244, 108, 132))
        img.paste(gradient, (0, 0))

    # Optional: add subtle rounded corners for iOS style
    if include_background:
        # Create rounded rectangle mask
        corner_radius = int(ss_size * 0.22)  # iOS-style rounded corners
        mask = Image.new('L', (ss_size, ss_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle(
            [0, 0, ss_size - 1, ss_size - 1],
            radius=corner_radius,
            fill=255
        )
        # Apply mask
        bg = Image.new('RGBA', (ss_size, ss_size), (0, 0, 0, 0))
        bg.paste(img, mask=mask)
        img = bg

    draw = ImageDraw.Draw(img)

    # Center of the image
    cx = ss_size // 2
    cy = int(ss_size * 0.52)  # Slightly below center for visual balance

    # Draw heart (white, prominent)
    heart_size = int(ss_size * 0.55)
    draw_heart_smooth(img, cx, cy, heart_size, (255, 255, 255, 255))

    # Draw arrow diagonally through the heart (from bottom-left to top-right)
    arrow_color = (232, 56, 88, 255)  # Coral to match background but visible on white

    # Arrow endpoints: from bottom-left to top-right, piercing the heart
    margin = int(ss_size * 0.12)
    ax1 = margin + int(ss_size * 0.05)
    ay1 = ss_size - margin - int(ss_size * 0.05)
    ax2 = ss_size - margin - int(ss_size * 0.05)
    ay2 = margin + int(ss_size * 0.05)

    arrow_thickness = int(ss_size * 0.022)
    arrow_head = int(ss_size * 0.08)

    draw_arrow(draw, ax1, ay1, ax2, ay2, arrow_thickness, arrow_color, arrow_head)

    # Downsample with high-quality resampling
    img = img.resize((size, size), Image.LANCZOS)

    img.save(output_path, 'PNG', quality=100)
    print(f"  Created: {output_path} ({size}x{size})")


def create_adaptive_icon(size, output_path):
    """Create adaptive icon foreground for Android (transparent bg)."""
    ss = 4
    ss_size = size * ss
    img = Image.new('RGBA', (ss_size, ss_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = ss_size // 2
    cy = int(ss_size * 0.52)

    # Smaller heart for safe zone
    heart_size = int(ss_size * 0.38)
    draw_heart_smooth(img, cx, cy, heart_size, (255, 255, 255, 255))

    # Arrow through heart
    arrow_color = (232, 56, 88, 255)
    safe_margin = int(ss_size * 0.22)  # Larger margin for safe zone
    ax1 = safe_margin
    ay1 = ss_size - safe_margin
    ax2 = ss_size - safe_margin
    ay2 = safe_margin

    arrow_thickness = int(ss_size * 0.018)
    arrow_head = int(ss_size * 0.06)
    draw_arrow(draw, ax1, ay1, ax2, ay2, arrow_thickness, arrow_color, arrow_head)

    img = img.resize((size, size), Image.LANCZOS)
    img.save(output_path, 'PNG', quality=100)
    print(f"  Created: {output_path} ({size}x{size})")


def create_splash_icon(size, output_path):
    """Create splash screen icon (coral heart + arrow, transparent bg)."""
    ss = 4
    ss_size = size * ss
    img = Image.new('RGBA', (ss_size, ss_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = ss_size // 2
    cy = int(ss_size * 0.52)

    # Coral heart
    heart_size = int(ss_size * 0.65)
    draw_heart_smooth(img, cx, cy, heart_size, (232, 56, 88, 255))

    # White arrow
    margin = int(ss_size * 0.1)
    ax1 = margin
    ay1 = ss_size - margin
    ax2 = ss_size - margin
    ay2 = margin

    arrow_thickness = int(ss_size * 0.025)
    arrow_head = int(ss_size * 0.09)
    draw_arrow(draw, ax1, ay1, ax2, ay2, arrow_thickness, (255, 255, 255, 255), arrow_head)

    img = img.resize((size, size), Image.LANCZOS)
    img.save(output_path, 'PNG', quality=100)
    print(f"  Created: {output_path} ({size}x{size})")


def create_favicon(size, output_path):
    """Create favicon (small, simplified)."""
    ss = 4
    ss_size = size * ss
    img = Image.new('RGBA', (ss_size, ss_size), (0, 0, 0, 0))

    # Gradient background
    gradient = create_gradient_fast(ss_size, (232, 56, 88), (244, 108, 132))
    img.paste(gradient, (0, 0))
    draw = ImageDraw.Draw(img)

    cx = ss_size // 2
    cy = int(ss_size * 0.52)

    # Heart
    heart_size = int(ss_size * 0.55)
    draw_heart_smooth(img, cx, cy, heart_size, (255, 255, 255, 255))

    # Simplified arrow (just a line with head)
    margin = int(ss_size * 0.15)
    draw_arrow(draw, margin, ss_size - margin, ss_size - margin, margin,
               int(ss_size * 0.03), (232, 56, 88, 255), int(ss_size * 0.1))

    img = img.resize((size, size), Image.LANCZOS)
    img.save(output_path, 'PNG', quality=100)
    print(f"  Created: {output_path} ({size}x{size})")


def main():
    print("Generating Arrow app icons (Cupid's Arrow + Heart)...\n")

    # Main app icon (1024x1024 for App Store)
    print("App Store icon:")
    create_arrow_icon(1024, 'frontend/assets/images/icon.png', include_background=True)
    create_arrow_icon(1024, '/sessions/jolly-elegant-bohr/mnt/outputs/arrow_icon_1024.png', include_background=True)

    # Adaptive icon foreground for Android (1024x1024)
    print("Android adaptive icon:")
    create_adaptive_icon(1024, 'frontend/assets/images/adaptive-icon.png')

    # Splash screen icon (200x200)
    print("Splash screen:")
    create_splash_icon(200, 'frontend/assets/images/splash-icon.png')

    # Favicon (48x48)
    print("Favicon:")
    create_favicon(48, 'frontend/assets/images/favicon.png')

    # Also generate a preview at 512x512 for easy viewing
    print("Preview icon:")
    create_arrow_icon(512, '/sessions/jolly-elegant-bohr/mnt/outputs/arrow_icon_512.png', include_background=True)
    create_splash_icon(512, '/sessions/jolly-elegant-bohr/mnt/outputs/arrow_splash_512.png')

    print("\nAll Arrow icons generated!")


if __name__ == "__main__":
    main()
