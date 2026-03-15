#!/usr/bin/env python3
"""
Icon Generator for Arrow App
Generates PNG icons from the SVG designs for App Store and Play Store
"""

import os

# Create the icon directories
os.makedirs('frontend/assets/images', exist_ok=True)

# Since we can't easily convert SVG to PNG without additional tools,
# we'll create the icons programmatically using PIL (Pillow)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Installing Pillow...")
    os.system("pip install Pillow")
    from PIL import Image, ImageDraw, ImageFont

def create_gradient(size, color1, color2):
    """Create a gradient background"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    
    for y in range(size):
        ratio = y / size
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))
    
    return img

def draw_heart(draw, center_x, center_y, size, color):
    """Draw a heart shape"""
    # Heart is made of two circles and a triangle
    radius = size // 4
    
    # Left circle
    left_circle_x = center_x - radius // 2
    left_circle_y = center_y - radius // 3
    draw.ellipse([
        left_circle_x - radius,
        left_circle_y - radius,
        left_circle_x + radius,
        left_circle_y + radius
    ], fill=color)
    
    # Right circle
    right_circle_x = center_x + radius // 2
    right_circle_y = center_y - radius // 3
    draw.ellipse([
        right_circle_x - radius,
        right_circle_y - radius,
        right_circle_x + radius,
        right_circle_y + radius
    ], fill=color)
    
    # Bottom triangle
    draw.polygon([
        (center_x - radius - radius // 2, center_y - radius // 4),
        (center_x + radius + radius // 2, center_y - radius // 4),
        (center_x, center_y + size // 2 - radius // 2)
    ], fill=color)

def create_app_icon(size, output_path, include_background=True):
    """Create the main app icon"""
    # Create image with transparent background
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    if include_background:
        # Coral pink gradient background
        gradient = create_gradient(size, (224, 64, 96), (236, 100, 128))
        img.paste(gradient, (0, 0))
        draw = ImageDraw.Draw(img)
    
    # White heart
    center = size // 2
    heart_size = int(size * 0.7)
    draw_heart(draw, center, int(center * 0.95), heart_size, (255, 255, 255, 255))
    
    # Add "b" letter in the heart
    try:
        font_size = int(size * 0.35)
        # Try to use a nice font, fall back to default
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", font_size)
            except:
                font = ImageFont.load_default()
        
        text = "b"
        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        text_x = center - text_width // 2
        text_y = center - text_height // 2 - int(size * 0.05)
        
        # Draw "b" in coral color
        draw.text((text_x, text_y), text, fill=(224, 64, 96, 255), font=font)
    except Exception as e:
        print(f"Could not add text: {e}")
    
    img.save(output_path, 'PNG')
    print(f"Created: {output_path}")

def create_adaptive_icon_foreground(size, output_path):
    """Create adaptive icon foreground for Android (transparent background)"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # White heart with safe zone padding (adaptive icons need 66% safe zone)
    center = size // 2
    heart_size = int(size * 0.5)  # Smaller for safe zone
    draw_heart(draw, center, int(center * 0.95), heart_size, (255, 255, 255, 255))
    
    # Add "b" letter
    try:
        font_size = int(size * 0.25)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", font_size)
            except:
                font = ImageFont.load_default()
        
        text = "b"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        text_x = center - text_width // 2
        text_y = center - text_height // 2 - int(size * 0.03)
        
        draw.text((text_x, text_y), text, fill=(224, 64, 96, 255), font=font)
    except Exception as e:
        print(f"Could not add text: {e}")
    
    img.save(output_path, 'PNG')
    print(f"Created: {output_path}")

def create_splash_icon(size, output_path):
    """Create splash screen icon"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Coral heart
    center = size // 2
    heart_size = int(size * 0.8)
    draw_heart(draw, center, int(center * 0.95), heart_size, (224, 64, 96, 255))
    
    # Add "b" letter in white
    try:
        font_size = int(size * 0.4)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", font_size)
            except:
                font = ImageFont.load_default()
        
        text = "b"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        text_x = center - text_width // 2
        text_y = center - text_height // 2 - int(size * 0.05)
        
        draw.text((text_x, text_y), text, fill=(255, 255, 255, 255), font=font)
    except Exception as e:
        print(f"Could not add text: {e}")
    
    img.save(output_path, 'PNG')
    print(f"Created: {output_path}")

def main():
    print("🎨 Generating Arrow app icons...\n")
    
    # Main app icon (1024x1024 for App Store)
    create_app_icon(1024, 'frontend/assets/images/icon.png', include_background=True)
    
    # Adaptive icon foreground for Android (1024x1024)
    create_adaptive_icon_foreground(1024, 'frontend/assets/images/adaptive-icon.png')
    
    # Splash screen icon (200x200)
    create_splash_icon(200, 'frontend/assets/images/splash-icon.png')
    
    # Favicon for web (48x48)
    create_app_icon(48, 'frontend/assets/images/favicon.png', include_background=True)
    
    print("\n✅ All icons generated successfully!")
    print("\nIcon files created:")
    print("  - frontend/assets/images/icon.png (1024x1024)")
    print("  - frontend/assets/images/adaptive-icon.png (1024x1024)")
    print("  - frontend/assets/images/splash-icon.png (200x200)")
    print("  - frontend/assets/images/favicon.png (48x48)")

if __name__ == "__main__":
    main()
