#!/usr/bin/env python3
"""
Theme 2 Detailed UI/UX Analysis
Analyzes images from Theme 2 to extract color schemes, UI components, 
layout patterns, typography, and animations.
"""

import os
from PIL import Image
import numpy as np
from collections import Counter
import json

IMAGE_DIR = "/home/raj/Downloads/ezgif-1a962da4dc5c8446-jpg"

def get_theme2_images():
    """Get all theme2 images sorted by frame number."""
    images = []
    for f in os.listdir(IMAGE_DIR):
        if f.endswith('theme2.jpg'):
            frame_num = int(f.replace('theme2.jpg', ''))
            images.append((frame_num, f))
    return sorted(images, key=lambda x: x[0])

def analyze_colors(img):
    """Extract dominant colors from image."""
    img_small = img.resize((100, 100))
    pixels = np.array(img_small).reshape(-1, 3)
    
    # Quantize colors
    quantized = (pixels // 32) * 32
    color_counts = Counter(map(tuple, quantized))
    
    # Get top colors
    top_colors = color_counts.most_common(8)
    return [(color, count) for color, count in top_colors]

def rgb_to_hex(rgb):
    """Convert RGB tuple to hex string."""
    return '#{:02x}{:02x}{:02x}'.format(*rgb)

def classify_color(rgb):
    """Classify a color into a category."""
    r, g, b = rgb
    
    # Check for whites/lights
    if r > 200 and g > 200 and b > 200:
        return "white/light"
    
    # Check for blacks/darks
    if r < 50 and g < 50 and b < 50:
        return "black/dark"
    
    # Check for grays
    if abs(r - g) < 30 and abs(g - b) < 30 and abs(r - b) < 30:
        if r > 150:
            return "light gray"
        elif r > 80:
            return "medium gray"
        else:
            return "dark gray"
    
    # Check for specific colors
    if r > g and r > b:
        if r > 200 and g < 100:
            return "red"
        elif r > 200 and g > 100 and g < 200:
            return "orange"
        elif r > 200 and g > 150:
            return "peach/salmon"
        else:
            return "warm red/brown"
    
    if g > r and g > b:
        if g > 150:
            return "green"
        else:
            return "dark green"
    
    if b > r and b > g:
        if b > 150 and r < 100:
            return "blue"
        elif r > 100:
            return "purple/violet"
        else:
            return "dark blue"
    
    if r > 150 and g > 150 and b < 100:
        return "yellow/gold"
    
    if r > 150 and b > 150 and g < 100:
        return "pink/magenta"
    
    if g > 150 and b > 150 and r < 100:
        return "cyan/teal"
    
    return "mixed"

def detect_ui_elements(img):
    """Detect UI elements based on image analysis."""
    width, height = img.size
    gray = img.convert('L')
    gray_arr = np.array(gray)
    
    elements = {
        "has_top_bar": False,
        "has_bottom_nav": False,
        "has_centered_content": False,
        "has_cards": False,
        "has_buttons": False,
        "has_input_fields": False,
        "layout_type": "unknown"
    }
    
    # Check top bar (status bar area)
    top_region = gray_arr[:int(height*0.08), :]
    top_variance = np.var(top_region)
    elements["has_top_bar"] = top_variance < 1000
    
    # Check bottom navigation
    bottom_region = gray_arr[int(height*0.9):, :]
    bottom_variance = np.var(bottom_region)
    bottom_mean = np.mean(bottom_region)
    elements["has_bottom_nav"] = bottom_variance > 500 and bottom_variance < 5000
    
    # Check for centered content (middle area variation)
    center_region = gray_arr[int(height*0.3):int(height*0.7), int(width*0.1):int(width*0.9)]
    center_variance = np.var(center_region)
    elements["has_centered_content"] = center_variance > 1000
    
    # Detect horizontal bands (potential cards)
    row_means = np.mean(gray_arr, axis=1)
    row_diffs = np.abs(np.diff(row_means))
    sharp_edges = np.sum(row_diffs > 20)
    elements["has_cards"] = sharp_edges > 5
    
    # Detect potential buttons (rounded rectangular regions)
    # Look for horizontal contrast changes in bottom half
    bottom_half = gray_arr[int(height*0.6):int(height*0.85), :]
    bottom_variance = np.var(bottom_half)
    elements["has_buttons"] = bottom_variance > 2000
    
    # Classify layout type
    if elements["has_bottom_nav"]:
        if elements["has_cards"]:
            elements["layout_type"] = "tabbed with cards"
        else:
            elements["layout_type"] = "tabbed"
    elif elements["has_centered_content"]:
        if elements["has_buttons"]:
            elements["layout_type"] = "form/input"
        else:
            elements["layout_type"] = "centered content"
    else:
        elements["layout_type"] = "full screen"
    
    return elements

def analyze_frame_section(images, start_idx, end_idx, section_name):
    """Analyze a section of frames."""
    section_images = [(num, name) for num, name in images if start_idx <= num <= end_idx]
    
    if not section_images:
        return None
    
    all_colors = Counter()
    color_categories = Counter()
    ui_elements_count = Counter()
    layout_types = Counter()
    
    sample_frames = []
    frame_progression = []
    
    for frame_num, filename in section_images:
        filepath = os.path.join(IMAGE_DIR, filename)
        try:
            img = Image.open(filepath).convert('RGB')
            
            # Analyze colors
            colors = analyze_colors(img)
            for color, count in colors:
                all_colors[color] += count
                category = classify_color(color)
                color_categories[category] += count
            
            # Analyze UI elements
            ui_elements = detect_ui_elements(img)
            for key, value in ui_elements.items():
                if isinstance(value, bool) and value:
                    ui_elements_count[key] += 1
                elif key == "layout_type":
                    layout_types[value] += 1
            
            # Track frame details for animation analysis
            frame_progression.append({
                "frame": frame_num,
                "layout": ui_elements["layout_type"],
                "has_cards": ui_elements["has_cards"],
                "has_buttons": ui_elements["has_buttons"]
            })
            
            # Sample a few frames for detailed analysis
            if len(sample_frames) < 5 or frame_num == start_idx or frame_num == end_idx:
                sample_frames.append({
                    "frame": frame_num,
                    "filename": filename,
                    "size": img.size,
                    "top_colors": [(rgb_to_hex(c), count) for c, count in colors[:5]]
                })
            
            img.close()
        except Exception as e:
            print(f"Error processing {filename}: {e}")
    
    # Get dominant colors
    top_colors = all_colors.most_common(10)
    
    # Analyze transitions
    transitions = []
    for i in range(1, len(frame_progression)):
        if frame_progression[i]["layout"] != frame_progression[i-1]["layout"]:
            transitions.append({
                "from_frame": frame_progression[i-1]["frame"],
                "to_frame": frame_progression[i]["frame"],
                "from_layout": frame_progression[i-1]["layout"],
                "to_layout": frame_progression[i]["layout"]
            })
    
    return {
        "section_name": section_name,
        "frame_range": f"{start_idx}-{end_idx}",
        "total_frames": len(section_images),
        "color_palette": {
            "dominant_colors": [(rgb_to_hex(c), count) for c, count in top_colors[:8]],
            "color_categories": dict(color_categories.most_common(10))
        },
        "ui_elements": {
            "summary": dict(ui_elements_count),
            "layout_types": dict(layout_types)
        },
        "sample_frames": sample_frames,
        "transitions": transitions,
        "animation_notes": f"Detected {len(transitions)} major layout transitions across {len(section_images)} frames"
    }

def analyze_visual_style(images):
    """Analyze overall visual style across all theme2 images."""
    # Sample every 10th image for style analysis
    sample_frames = [img for img in images if img[0] % 10 == 1][:20]
    
    brightness_values = []
    contrast_values = []
    
    for frame_num, filename in sample_frames:
        filepath = os.path.join(IMAGE_DIR, filename)
        try:
            img = Image.open(filepath).convert('L')
            arr = np.array(img)
            brightness_values.append(np.mean(arr))
            contrast_values.append(np.std(arr))
            img.close()
        except:
            pass
    
    avg_brightness = np.mean(brightness_values) if brightness_values else 0
    avg_contrast = np.mean(contrast_values) if contrast_values else 0
    
    style = {
        "brightness": "light" if avg_brightness > 180 else "medium" if avg_brightness > 100 else "dark",
        "contrast": "high" if avg_contrast > 60 else "medium" if avg_contrast > 40 else "low",
        "avg_brightness_value": round(avg_brightness, 2),
        "avg_contrast_value": round(avg_contrast, 2)
    }
    
    return style

def generate_report(analysis_results, visual_style):
    """Generate a detailed markdown report."""
    report = """# Theme 2 Detailed UI/UX Analysis

## Overall Visual Style

- **Brightness Level:** {brightness} (avg: {brightness_val})
- **Contrast Level:** {contrast} (avg: {contrast_val})

---

""".format(
        brightness=visual_style["brightness"],
        brightness_val=visual_style["avg_brightness_value"],
        contrast=visual_style["contrast"],
        contrast_val=visual_style["avg_contrast_value"]
    )
    
    for section in analysis_results:
        if section is None:
            continue
            
        report += f"""## {section['section_name']}
**Frames:** {section['frame_range']} ({section['total_frames']} frames analyzed)

### 1. Color Scheme
**Dominant Colors:**
"""
        for color, count in section['color_palette']['dominant_colors'][:6]:
            report += f"- `{color}` (frequency: {count})\n"
        
        report += "\n**Color Categories:**\n"
        for category, count in sorted(section['color_palette']['color_categories'].items(), key=lambda x: -x[1])[:5]:
            report += f"- {category}: {count}\n"
        
        report += f"""
### 2. UI Components
**Element Detection Summary:**
"""
        for element, count in section['ui_elements']['summary'].items():
            percentage = (count / section['total_frames']) * 100
            report += f"- {element.replace('has_', '').replace('_', ' ').title()}: {percentage:.1f}% of frames\n"
        
        report += "\n**Layout Types Distribution:**\n"
        for layout, count in section['ui_elements']['layout_types'].items():
            percentage = (count / section['total_frames']) * 100
            report += f"- {layout}: {percentage:.1f}%\n"
        
        report += f"""
### 3. Layout Patterns
Based on frame analysis, this section primarily uses **{max(section['ui_elements']['layout_types'], key=section['ui_elements']['layout_types'].get) if section['ui_elements']['layout_types'] else 'unknown'}** layout pattern.

### 4. Animation/Transitions
{section['animation_notes']}
"""
        if section['transitions']:
            report += "\n**Detected Transitions:**\n"
            for trans in section['transitions'][:5]:
                report += f"- Frame {trans['from_frame']} → {trans['to_frame']}: {trans['from_layout']} → {trans['to_layout']}\n"
        
        report += "\n---\n\n"
    
    return report

def main():
    print("=" * 60)
    print("THEME 2 DETAILED UI/UX ANALYSIS")
    print("=" * 60)
    
    # Get all theme2 images
    images = get_theme2_images()
    print(f"\nFound {len(images)} Theme 2 images")
    print(f"Frame range: {images[0][0]} to {images[-1][0]}")
    
    # Define sections to analyze
    sections = [
        (1, 10, "Section 1: Opening/Welcome Screens"),
        (11, 30, "Section 2: Quiz/Questionnaire Screens"),
        (31, 50, "Section 3: Profile/Options Screens"),
        (51, 70, "Section 4: Date Ideas/Planning"),
        (71, 100, "Section 5: Extended Features (71-100)"),
        (101, 130, "Section 6: Extended Features (101-130)"),
        (131, 170, "Section 7: Final Screens (131-170)")
    ]
    
    # Analyze each section
    print("\nAnalyzing sections...")
    analysis_results = []
    for start, end, name in sections:
        print(f"  Analyzing {name}...")
        result = analyze_frame_section(images, start, end, name)
        analysis_results.append(result)
    
    # Analyze overall visual style
    print("  Analyzing overall visual style...")
    visual_style = analyze_visual_style(images)
    
    # Generate report
    print("\nGenerating report...")
    report = generate_report(analysis_results, visual_style)
    
    # Save report
    report_path = "/home/raj/app/theme2_analysis.md"
    with open(report_path, 'w') as f:
        f.write(report)
    print(f"\nReport saved to: {report_path}")
    
    # Print summary to console
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    print(f"\n📊 Overall Style:")
    print(f"   • Brightness: {visual_style['brightness']} ({visual_style['avg_brightness_value']})")
    print(f"   • Contrast: {visual_style['contrast']} ({visual_style['avg_contrast_value']})")
    
    for section in analysis_results:
        if section:
            print(f"\n📁 {section['section_name']}:")
            print(f"   • Frames: {section['frame_range']}")
            print(f"   • Primary layout: {max(section['ui_elements']['layout_types'], key=section['ui_elements']['layout_types'].get) if section['ui_elements']['layout_types'] else 'N/A'}")
            top_colors = section['color_palette']['dominant_colors'][:3]
            print(f"   • Top colors: {', '.join([c[0] for c in top_colors])}")
            print(f"   • Transitions detected: {len(section['transitions'])}")

if __name__ == "__main__":
    main()
