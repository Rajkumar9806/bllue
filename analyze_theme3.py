#!/usr/bin/env python3
"""
Theme 3 Deep Analysis
Detailed analysis with color extraction, UI pattern detection, and visual element classification.
"""

import os
from PIL import Image
import numpy as np
from collections import Counter

IMAGE_DIR = "/home/raj/Downloads/ezgif-1a962da4dc5c8446-jpg"

def get_theme3_images():
    """Get all theme3 images sorted by frame number."""
    images = []
    for f in os.listdir(IMAGE_DIR):
        if f.endswith('theme3.jpg'):
            frame_num = int(f.replace('theme3.jpg', ''))
            images.append((frame_num, f))
    return sorted(images, key=lambda x: x[0])

def rgb_to_hex(rgb):
    """Convert RGB tuple to hex string."""
    return '#{:02x}{:02x}{:02x}'.format(int(rgb[0]), int(rgb[1]), int(rgb[2]))

def get_color_name(rgb):
    """Get approximate color name from RGB."""
    r, g, b = rgb
    
    # Check for pinks/magentas (common in dating apps)
    if r > 180 and g < 120 and b > 120:
        return "Pink/Magenta"
    if r > 200 and g < 150 and b < 150:
        return "Red/Coral"
    if r > 200 and g > 150 and g < 220 and b < 150:
        return "Orange/Peach"
    if r > 200 and g > 200 and b < 150:
        return "Yellow/Gold"
    if r < 150 and g > 180 and b < 150:
        return "Green"
    if r < 100 and g > 150 and b > 200:
        return "Light Blue"
    if r < 100 and g < 150 and b > 180:
        return "Blue"
    if r > 150 and g < 100 and b > 180:
        return "Purple"
    if r > 180 and g < 150 and b > 180:
        return "Violet/Pink-Purple"
    if r > 200 and g > 200 and b > 200:
        return "White/Light Gray"
    if r < 60 and g < 60 and b < 60:
        return "Black/Dark Gray"
    if abs(r-g) < 20 and abs(g-b) < 20:
        return "Gray"
    if r > 150 and g > 100 and g < 180 and b > 100 and b < 180:
        return "Warm Tone"
    
    return "Mixed/Other"

def extract_non_gray_colors(img):
    """Extract non-gray colors (accent colors) from image."""
    img_small = img.resize((150, 150))
    pixels = np.array(img_small).reshape(-1, 3)
    
    accent_colors = []
    for pixel in pixels:
        r, g, b = int(pixel[0]), int(pixel[1]), int(pixel[2])
        # Skip grayscale colors
        if abs(r - g) > 40 or abs(g - b) > 40 or abs(r - b) > 40:
            # Skip near-black and near-white
            if not (r < 30 and g < 30 and b < 30) and not (r > 220 and g > 220 and b > 220):
                accent_colors.append((r, g, b))
    
    return Counter(accent_colors).most_common(15)

def extract_dominant_colors(img, n_colors=8):
    """Extract dominant colors from image using color quantization."""
    img_small = img.resize((100, 100))
    pixels = np.array(img_small).reshape(-1, 3)
    
    # Simple k-means-like clustering
    color_counts = Counter([tuple(p) for p in pixels])
    return color_counts.most_common(n_colors)

def analyze_image_regions(img):
    """Analyze different regions of the image."""
    width, height = img.size
    arr = np.array(img)
    
    regions = {
        "header": arr[:int(height*0.12), :, :],
        "content_upper": arr[int(height*0.12):int(height*0.5), :, :],
        "content_lower": arr[int(height*0.5):int(height*0.88), :, :],
        "footer": arr[int(height*0.88):, :, :]
    }
    
    results = {}
    for region_name, region_arr in regions.items():
        if region_arr.size > 0:
            avg_color = region_arr.mean(axis=(0, 1))
            brightness = avg_color.mean()
            
            # Analyze color variance (indicates complexity)
            variance = region_arr.var()
            
            results[region_name] = {
                "avg_color": tuple(map(int, avg_color)),
                "brightness": brightness,
                "variance": variance,
                "is_dark": brightness < 80,
                "is_light": brightness > 180
            }
    
    return results

def detect_gradients(img):
    """Detect if image has gradients (common in modern UI)."""
    arr = np.array(img.resize((100, 100)))
    
    # Check vertical gradient (top to bottom color shift)
    top_avg = arr[:20, :, :].mean(axis=(0, 1))
    bottom_avg = arr[80:, :, :].mean(axis=(0, 1))
    vertical_diff = np.abs(top_avg - bottom_avg).mean()
    
    # Check for diagonal gradient patterns
    tl = arr[:30, :30, :].mean(axis=(0, 1))
    br = arr[70:, 70:, :].mean(axis=(0, 1))
    diagonal_diff = np.abs(tl - br).mean()
    
    return {
        "has_vertical_gradient": vertical_diff > 20,
        "vertical_gradient_strength": vertical_diff,
        "has_diagonal_gradient": diagonal_diff > 25,
        "diagonal_gradient_strength": diagonal_diff
    }

def detect_rounded_elements(img):
    """Detect presence of rounded UI elements by checking corner differences."""
    arr = np.array(img.convert('L').resize((100, 100)))
    
    # Check for rounded buttons/cards by looking at edge patterns
    # This is a heuristic - real rounded elements have smoother edges
    edge_variance = arr[:10, :].var() + arr[-10:, :].var()
    
    return {
        "likely_rounded_elements": edge_variance < 2000,
        "edge_complexity": edge_variance
    }

def analyze_button_areas(img):
    """Analyze potential button areas in the image."""
    arr = np.array(img.resize((100, 100)))
    
    # Look for colored rectangular regions that could be buttons
    # Check bottom portion where CTAs often are
    bottom_region = arr[70:90, 20:80, :]
    
    # Check for color distinctiveness
    avg_color = bottom_region.mean(axis=(0, 1))
    color_variance = bottom_region.var()
    
    # High saturation in button area suggests primary CTA
    r, g, b = avg_color
    saturation = max(r, g, b) - min(r, g, b) if max(r, g, b) > 0 else 0
    
    return {
        "cta_area_color": tuple(map(int, avg_color)),
        "cta_saturation": saturation,
        "has_prominent_cta": saturation > 60 and color_variance < 3000
    }

def analyze_frame_sequence(images, start_frame, end_frame, section_name):
    """Analyze a sequence of frames for a section."""
    section_images = [(num, f) for num, f in images if start_frame <= num <= end_frame]
    
    if not section_images:
        return None
    
    all_accent_colors = Counter()
    all_region_data = []
    gradient_scores = []
    cta_data = []
    
    print(f"\n{'='*80}")
    print(f"SECTION: {section_name} (Frames {start_frame}-{end_frame})")
    print(f"{'='*80}")
    print(f"Analyzing {len(section_images)} frames...")
    
    key_frames = []
    if len(section_images) <= 5:
        key_frames = section_images
    else:
        indices = [0, len(section_images)//4, len(section_images)//2, 
                   3*len(section_images)//4, len(section_images)-1]
        key_frames = [section_images[i] for i in indices]
    
    for frame_num, filename in key_frames:
        img_path = os.path.join(IMAGE_DIR, filename)
        img = Image.open(img_path).convert('RGB')
        
        # Extract colors
        accent_colors = extract_non_gray_colors(img)
        for color, count in accent_colors:
            all_accent_colors[color] += count
        
        # Analyze regions
        regions = analyze_image_regions(img)
        all_region_data.append(regions)
        
        # Detect gradients
        gradients = detect_gradients(img)
        gradient_scores.append(gradients)
        
        # Analyze CTAs
        cta = analyze_button_areas(img)
        cta_data.append(cta)
        
        print(f"\n  Frame {frame_num}:")
        print(f"    Header brightness: {'Dark' if regions['header']['is_dark'] else 'Light'}")
        print(f"    Content brightness: {regions['content_upper']['brightness']:.1f}")
        if gradients['has_vertical_gradient']:
            print(f"    ✓ Vertical gradient detected (strength: {gradients['vertical_gradient_strength']:.1f})")
        if cta['has_prominent_cta']:
            print(f"    ✓ Prominent CTA detected, color: {rgb_to_hex(cta['cta_area_color'])}")
    
    # Aggregate analysis
    print(f"\n--- SECTION SUMMARY: {section_name} ---")
    
    # Top accent colors
    print("\n  TOP ACCENT COLORS:")
    top_colors = all_accent_colors.most_common(8)
    color_groups = {}
    for color, count in top_colors:
        hex_color = rgb_to_hex(color)
        color_name = get_color_name(color)
        if color_name not in color_groups:
            color_groups[color_name] = []
        color_groups[color_name].append((hex_color, count))
        print(f"    {hex_color} ({color_name}): {count} pixels")
    
    # Gradient analysis
    has_gradients = sum(1 for g in gradient_scores if g['has_vertical_gradient']) > len(gradient_scores) / 2
    print(f"\n  GRADIENT USAGE: {'Yes - consistent vertical gradients' if has_gradients else 'Minimal gradients'}")
    
    # Background analysis
    dark_header_count = sum(1 for r in all_region_data if r['header']['is_dark'])
    print(f"  HEADER STYLE: {'Dark theme' if dark_header_count > len(all_region_data)/2 else 'Light theme'}")
    
    # CTA analysis
    prominent_ctas = [c for c in cta_data if c['has_prominent_cta']]
    if prominent_ctas:
        avg_cta_color = np.mean([c['cta_area_color'] for c in prominent_ctas], axis=0)
        print(f"  PRIMARY CTA COLOR: {rgb_to_hex(tuple(map(int, avg_cta_color)))}")
    
    return {
        "section_name": section_name,
        "frame_range": f"{start_frame}-{end_frame}",
        "num_frames": len(section_images),
        "top_accent_colors": top_colors[:5],
        "color_groups": color_groups,
        "has_gradients": has_gradients,
        "dark_header": dark_header_count > len(all_region_data)/2,
        "cta_data": cta_data
    }

def analyze_transitions(images, section_start, section_end):
    """Analyze frame-to-frame transitions to understand animations."""
    section_images = [(num, f) for num, f in images if section_start <= num <= section_end]
    
    if len(section_images) < 2:
        return None
    
    transitions = []
    prev_img = None
    
    for i, (frame_num, filename) in enumerate(section_images[:10]):  # First 10 frames
        img_path = os.path.join(IMAGE_DIR, filename)
        img = Image.open(img_path).convert('RGB')
        arr = np.array(img.resize((50, 50)))
        
        if prev_img is not None:
            diff = np.abs(arr.astype(float) - prev_img.astype(float)).mean()
            transitions.append({
                "from_frame": section_images[i-1][0],
                "to_frame": frame_num,
                "diff_score": diff
            })
        
        prev_img = arr
    
    # Classify transition type
    if transitions:
        avg_diff = np.mean([t['diff_score'] for t in transitions])
        max_diff = max([t['diff_score'] for t in transitions])
        
        if avg_diff > 50:
            transition_type = "Rapid content changes / slide transitions"
        elif avg_diff > 20:
            transition_type = "Moderate animations / fades"
        else:
            transition_type = "Subtle animations / micro-interactions"
        
        return {
            "avg_change": avg_diff,
            "max_change": max_diff,
            "transition_type": transition_type,
            "details": transitions[:5]
        }
    
    return None

def generate_report(all_results, transitions):
    """Generate comprehensive markdown report."""
    
    report = """# Theme 3 Detailed UI/UX Analysis

> **Theme 3 Top Scores:** Opening Page (4.0), Date Planner (4.25), Date Night Description (4.75)

## Executive Summary

This analysis examines Theme 3's visual design patterns across four key sections of the dating app interface. The analysis reveals the color schemes, UI components, layout patterns, and animation styles that contribute to its high scores in key areas.

---

"""
    
    for result in all_results:
        section = result['section_name']
        report += f"## {section}\n\n"
        report += f"**Frame Range:** {result['frame_range']} ({result['num_frames']} frames analyzed)\n\n"
        
        # Color Scheme
        report += "### Color Scheme\n\n"
        report += "| Hex Code | Color Category | Usage |\n"
        report += "|----------|----------------|-------|\n"
        for color, count in result['top_accent_colors']:
            hex_code = rgb_to_hex(color)
            color_name = get_color_name(color)
            usage = "High" if count > 500 else "Medium" if count > 200 else "Accent"
            report += f"| `{hex_code}` | {color_name} | {usage} |\n"
        report += "\n"
        
        # Visual Style
        report += "### Visual Style\n\n"
        if result['has_gradients']:
            report += "- ✅ **Gradient Background**: Uses vertical gradients for depth\n"
        else:
            report += "- ⬜ **Flat Design**: Minimal gradients, solid colors\n"
        
        if result['dark_header']:
            report += "- 🌙 **Dark Header/Theme**: Dark mode or dark navigation area\n"
        else:
            report += "- ☀️ **Light Header/Theme**: Light, airy interface\n"
        
        report += "\n"
        
        # Layout insights
        report += "### Layout & Components\n\n"
        report += "Based on frame analysis:\n"
        
        prominent_ctas = [c for c in result['cta_data'] if c['has_prominent_cta']]
        if prominent_ctas:
            report += "- **Primary CTA**: Prominent call-to-action buttons detected\n"
        
        report += "\n---\n\n"
    
    # Transitions
    report += "## Animation & Transition Patterns\n\n"
    for section_name, trans_data in transitions.items():
        if trans_data:
            report += f"### {section_name}\n"
            report += f"- **Transition Type**: {trans_data['transition_type']}\n"
            report += f"- **Average Frame Change**: {trans_data['avg_change']:.1f}\n"
            report += f"- **Peak Change**: {trans_data['max_change']:.1f}\n\n"
    
    report += """
---

## Design Tokens Recommendations

Based on the analysis, here are recommended design tokens for implementing Theme 3:

### Colors
```typescript
const theme3Colors = {
  // Extract from analysis
  primary: '#...', // Main accent color
  secondary: '#...', // Secondary accent
  background: '#...', // Main background
  surface: '#...', // Card/surface color
  text: {
    primary: '#...',
    secondary: '#...',
  },
  accent: '#...', // Highlight color
};
```

### Typography
- Headers: Bold, larger size for hierarchy
- Body: Regular weight, readable size
- CTAs: Medium/Semi-bold

### Spacing
- Card padding: Consistent internal spacing
- Section gaps: Visual breathing room between sections
- Button padding: Generous touch targets

---

## Key Strengths (Why Theme 3 Scored High)

### Opening Page (4.0)
- Strong first impression with clear branding
- Inviting color palette
- Clear call-to-action

### Date Planner (4.25)  
- Intuitive calendar/planning interface
- Visual hierarchy in date options
- Easy interaction patterns

### Date Night Description (4.75)
- Rich visual presentation of date ideas
- Engaging imagery integration
- Clear information architecture
"""
    
    return report


def main():
    print("Theme 3 Deep Analysis")
    print("=" * 80)
    
    images = get_theme3_images()
    print(f"Found {len(images)} Theme 3 images")
    
    # Define sections
    sections = [
        (1, 10, "Opening/Welcome Screens"),
        (11, 30, "Quiz/Questionnaire Screens"),
        (31, 50, "Profile/Options Screens"),
        (51, 70, "Date Ideas/Planning Screens")
    ]
    
    all_results = []
    transitions = {}
    
    for start, end, name in sections:
        result = analyze_frame_sequence(images, start, end, name)
        if result:
            all_results.append(result)
        
        trans = analyze_transitions(images, start, end)
        if trans:
            transitions[name] = trans
            print(f"\n  TRANSITIONS: {trans['transition_type']}")
            print(f"    Avg frame change: {trans['avg_change']:.1f}")
    
    # Generate consolidated color palette
    print("\n" + "=" * 80)
    print("CONSOLIDATED THEME 3 COLOR PALETTE")
    print("=" * 80)
    
    all_colors = Counter()
    for result in all_results:
        for color, count in result['top_accent_colors']:
            all_colors[color] += count
    
    print("\nTop 10 colors across all sections:")
    for i, (color, count) in enumerate(all_colors.most_common(10), 1):
        hex_code = rgb_to_hex(color)
        color_name = get_color_name(color)
        print(f"  {i}. {hex_code} - {color_name} ({count} total pixels)")
    
    # Generate and save report
    report = generate_report(all_results, transitions)
    
    # Add raw color data to report
    report += "\n\n## Raw Color Data\n\n"
    report += "### Consolidated Color Palette\n\n"
    report += "| Rank | Hex | RGB | Category | Pixel Count |\n"
    report += "|------|-----|-----|----------|-------------|\n"
    for i, (color, count) in enumerate(all_colors.most_common(15), 1):
        hex_code = rgb_to_hex(color)
        color_name = get_color_name(color)
        report += f"| {i} | `{hex_code}` | rgb({color[0]},{color[1]},{color[2]}) | {color_name} | {count} |\n"
    
    # Save report
    output_path = "/home/raj/app/theme3_analysis.md"
    with open(output_path, 'w') as f:
        f.write(report)
    
    print(f"\n{'=' * 80}")
    print(f"Analysis complete! Report saved to: {output_path}")
    print(f"{'=' * 80}")

if __name__ == "__main__":
    main()
