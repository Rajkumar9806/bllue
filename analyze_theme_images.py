"""
Theme 1 Image Analysis Script
Analyzes color schemes and basic visual properties from Theme 1 frames.
"""

import os
from collections import Counter
from pathlib import Path

try:
    from PIL import Image
    import colorsys
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.run(["pip", "install", "Pillow"])
    from PIL import Image
    import colorsys


def rgb_to_hex(r, g, b):
    """Convert RGB to hex color."""
    return f"#{r:02x}{g:02x}{b:02x}"


def get_color_name(r, g, b):
    """Get approximate color name from RGB."""
    h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
    
    if v < 0.2:
        return "black"
    if s < 0.1 and v > 0.9:
        return "white"
    if s < 0.2:
        return "gray"
    
    hue = h * 360
    if hue < 15 or hue >= 345:
        return "red"
    elif hue < 45:
        return "orange"
    elif hue < 75:
        return "yellow"
    elif hue < 150:
        return "green"
    elif hue < 210:
        return "cyan"
    elif hue < 270:
        return "blue"
    elif hue < 300:
        return "purple"
    else:
        return "pink"


def analyze_image(image_path):
    """Analyze a single image for dominant colors."""
    try:
        img = Image.open(image_path)
        img = img.convert('RGB')
        
        # Resize for faster processing
        img_small = img.resize((100, 100))
        
        # Get all pixels
        pixels = list(img_small.getdata())
        
        # Quantize colors (reduce to 16 colors)
        color_counts = Counter()
        for r, g, b in pixels:
            # Quantize to reduce color space
            r_q = (r // 32) * 32
            g_q = (g // 32) * 32
            b_q = (b // 32) * 32
            color_counts[(r_q, g_q, b_q)] += 1
        
        return color_counts.most_common(5), img.size
    except Exception as e:
        return None, str(e)


def analyze_theme1_section(image_dir, start, end, section_name):
    """Analyze a section of Theme 1 images."""
    print(f"\n{'='*60}")
    print(f"  {section_name} (frames {start}-{end})")
    print(f"{'='*60}")
    
    all_colors = Counter()
    analyzed_count = 0
    
    for i in range(start, end + 1):
        filename = f"{i}theme1.jpg"
        filepath = os.path.join(image_dir, filename)
        
        if os.path.exists(filepath):
            colors, size = analyze_image(filepath)
            if colors:
                analyzed_count += 1
                for color, count in colors:
                    all_colors[color] += count
    
    print(f"\nAnalyzed {analyzed_count} images")
    print(f"\nDominant Colors:")
    print("-" * 40)
    
    for color, count in all_colors.most_common(8):
        r, g, b = color
        hex_color = rgb_to_hex(r, g, b)
        color_name = get_color_name(r, g, b)
        percentage = (count / sum(all_colors.values())) * 100
        print(f"  {hex_color}  ({color_name:8}) - {percentage:.1f}%")
    
    return all_colors


def main():
    image_dir = "/home/raj/Downloads/ezgif-1a962da4dc5c8446-jpg"
    
    print("\n" + "="*60)
    print("  THEME 1 IMAGE ANALYSIS")
    print("="*60)
    
    # Analyze each section
    sections = [
        (1, 10, "Opening/Welcome Screens"),
        (11, 30, "Quiz/Questionnaire Screens"),
        (31, 50, "Profile/Options Screens"),
        (51, 70, "Date Ideas/Planning Screens"),
        (71, 100, "Additional Screens"),
        (101, 130, "Extended Flow Part 1"),
        (131, 170, "Extended Flow Part 2"),
        (171, 230, "Final Screens"),
    ]
    
    overall_colors = Counter()
    
    for start, end, name in sections:
        colors = analyze_theme1_section(image_dir, start, end, name)
        overall_colors.update(colors)
    
    # Overall summary
    print("\n" + "="*60)
    print("  OVERALL COLOR PALETTE SUMMARY")
    print("="*60)
    
    print("\nTop 10 Colors Across All Theme 1 Frames:")
    print("-" * 40)
    for color, count in overall_colors.most_common(10):
        r, g, b = color
        hex_color = rgb_to_hex(r, g, b)
        color_name = get_color_name(r, g, b)
        percentage = (count / sum(overall_colors.values())) * 100
        print(f"  {hex_color}  ({color_name:8}) - {percentage:.1f}%")
    
    # Identify color categories
    print("\n\nColor Category Distribution:")
    print("-" * 40)
    categories = Counter()
    for (r, g, b), count in overall_colors.items():
        name = get_color_name(r, g, b)
        categories[name] += count
    
    total = sum(categories.values())
    for name, count in categories.most_common():
        percentage = (count / total) * 100
        print(f"  {name:10} - {percentage:.1f}%")


if __name__ == "__main__":
    main()
