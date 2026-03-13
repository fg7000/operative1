#!/usr/bin/env python3
"""
Generate Chrome Web Store assets.
All images: PNG, no alpha channel.
"""

from PIL import Image, ImageDraw, ImageFont
import os

BG_COLOR = (26, 26, 26)  # #1a1a1a
TEXT_COLOR = (255, 255, 255)
GRAY_TEXT = (180, 180, 180)
DARK_GRAY = (100, 100, 100)
GREEN = (34, 197, 94)  # #22c55e

DOWNLOADS = os.path.expanduser("~/Downloads")


def get_font(size: int):
    """Load a good font."""
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    return ImageFont.load_default()


def get_regular_font(size: int):
    """Load a regular weight font."""
    font_paths = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    return ImageFont.load_default()


def center_text(draw, text, font, y, width, color):
    """Draw centered text."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (width - text_width) // 2
    draw.text((x, y), text, font=font, fill=color)


def create_store_icon():
    """Create 128x128 store icon (no alpha)."""
    size = 128
    img = Image.new('RGB', (size, size), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Draw rounded rectangle
    corner_radius = size // 6
    draw.rounded_rectangle(
        [(0, 0), (size - 1, size - 1)],
        radius=corner_radius,
        fill=BG_COLOR
    )

    # Draw "OP1" text
    font = get_font(int(size * 0.32))
    text = "OP1"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2 - bbox[0]
    y = (size - text_height) // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=TEXT_COLOR)

    path = os.path.join(DOWNLOADS, "store-icon-128.png")
    img.save(path, 'PNG')
    print(f"Created {path}")
    return img


def create_screenshot():
    """Create 1280x800 screenshot (no alpha)."""
    width, height = 1280, 800
    img = Image.new('RGB', (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Title
    title_font = get_font(48)
    center_text(draw, "AI Reply Marketing", title_font, 60, width, TEXT_COLOR)

    # Subtitle
    subtitle_font = get_regular_font(24)
    center_text(draw, "Find conversations. Draft replies. Post from your browser.", subtitle_font, 130, width, GRAY_TEXT)

    # Mock extension popup (left side)
    popup_x, popup_y = 180, 220
    popup_w, popup_h = 320, 380

    # Popup background
    draw.rounded_rectangle(
        [(popup_x, popup_y), (popup_x + popup_w, popup_y + popup_h)],
        radius=12,
        fill=(255, 255, 255)
    )

    # Popup header
    draw.rectangle([(popup_x, popup_y), (popup_x + popup_w, popup_y + 50)], fill=(250, 250, 250))
    header_font = get_font(14)
    draw.text((popup_x + 20, popup_y + 18), "OPERATIVE1", font=header_font, fill=(17, 17, 17))

    # "Connected" status
    status_y = popup_y + 70
    draw.ellipse([(popup_x + 20, status_y), (popup_x + 32, status_y + 12)], fill=GREEN)
    status_font = get_font(16)
    draw.text((popup_x + 42, status_y - 2), "Connected to Twitter", font=status_font, fill=(17, 17, 17))

    # Product name
    product_y = popup_y + 110
    product_font = get_regular_font(14)
    draw.text((popup_x + 20, product_y), "Product: BurnChat", font=product_font, fill=(102, 102, 102))

    # Security info box
    security_y = popup_y + 160
    draw.rounded_rectangle(
        [(popup_x + 15, security_y), (popup_x + popup_w - 15, security_y + 100)],
        radius=8,
        fill=(248, 250, 248)
    )

    check_font = get_regular_font(12)
    checks = [
        "✓ Posts from YOUR browser",
        "✓ Credentials never leave browser",
        "✓ Disconnect anytime"
    ]
    for i, check in enumerate(checks):
        draw.text((popup_x + 30, security_y + 15 + i * 28), check, font=check_font, fill=(22, 101, 52))

    # Disconnect button
    btn_y = popup_y + 290
    draw.rounded_rectangle(
        [(popup_x + 20, btn_y), (popup_x + popup_w - 20, btn_y + 40)],
        radius=8,
        fill=(245, 245, 245)
    )
    btn_font = get_font(14)
    center_text(draw, "Disconnect", btn_font, btn_y + 12, popup_w, (102, 102, 102))
    draw.text((popup_x + (popup_w - 80) // 2, btn_y + 12), "Disconnect", font=btn_font, fill=(102, 102, 102))

    # Mock dashboard (right side)
    dash_x, dash_y = 580, 220
    dash_w, dash_h = 520, 380

    # Dashboard background
    draw.rounded_rectangle(
        [(dash_x, dash_y), (dash_x + dash_w, dash_y + dash_h)],
        radius=12,
        fill=(255, 255, 255)
    )

    # Dashboard header
    draw.rectangle([(dash_x, dash_y), (dash_x + dash_w, dash_y + 50)], fill=(250, 250, 250))
    draw.text((dash_x + 20, dash_y + 16), "Reply Queue", font=get_font(18), fill=(17, 17, 17))

    # Green connected banner
    banner_y = dash_y + 60
    draw.rounded_rectangle(
        [(dash_x + 15, banner_y), (dash_x + dash_w - 15, banner_y + 35)],
        radius=6,
        fill=(232, 245, 233)
    )
    draw.ellipse([(dash_x + 25, banner_y + 12), (dash_x + 35, banner_y + 22)], fill=GREEN)
    draw.text((dash_x + 45, banner_y + 9), "Extension connected", font=get_regular_font(13), fill=(46, 125, 50))

    # Queue items
    for i in range(3):
        item_y = banner_y + 55 + i * 90

        # Item card
        draw.rounded_rectangle(
            [(dash_x + 15, item_y), (dash_x + dash_w - 15, item_y + 80)],
            radius=8,
            fill=(250, 250, 250)
        )

        # Platform badge
        badge_colors = [(29, 161, 242), (255, 69, 0), (0, 119, 181)]  # Twitter, Reddit, LinkedIn
        platforms = ["twitter", "reddit", "linkedin"]
        draw.rounded_rectangle(
            [(dash_x + 25, item_y + 10), (dash_x + 85, item_y + 28)],
            radius=10,
            fill=badge_colors[i]
        )
        draw.text((dash_x + 35, item_y + 11), platforms[i].upper()[:3], font=get_font(10), fill=TEXT_COLOR)

        # Mock text lines
        for j in range(2):
            line_y = item_y + 40 + j * 16
            line_w = 300 - j * 80
            draw.rounded_rectangle(
                [(dash_x + 25, line_y), (dash_x + 25 + line_w, line_y + 10)],
                radius=3,
                fill=(230, 230, 230)
            )

        # Approve button
        draw.rounded_rectangle(
            [(dash_x + dash_w - 110, item_y + 25), (dash_x + dash_w - 25, item_y + 55)],
            radius=6,
            fill=(17, 17, 17)
        )
        draw.text((dash_x + dash_w - 95, item_y + 32), "Approve", font=get_font(12), fill=TEXT_COLOR)

    # Brand footer
    footer_font = get_font(14)
    center_text(draw, "OPERATIVE1", footer_font, height - 60, width, DARK_GRAY)

    path = os.path.join(DOWNLOADS, "screenshot-1280x800.png")
    img.save(path, 'PNG')
    print(f"Created {path}")
    return img


def create_promo_tile():
    """Create 440x280 promo tile (no alpha)."""
    width, height = 440, 280
    img = Image.new('RGB', (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # "OP1" large
    title_font = get_font(72)
    center_text(draw, "OP1", title_font, 60, width, TEXT_COLOR)

    # Tagline
    tagline_font = get_regular_font(20)
    center_text(draw, "AI Reply Marketing Engine", tagline_font, 170, width, GRAY_TEXT)

    # Brand
    brand_font = get_font(14)
    center_text(draw, "OPERATIVE1", brand_font, 230, width, DARK_GRAY)

    path = os.path.join(DOWNLOADS, "promo-440x280.png")
    img.save(path, 'PNG')
    print(f"Created {path}")
    return img


def create_marquee_tile():
    """Create 1400x560 marquee promo tile (no alpha, JPEG compatible)."""
    width, height = 1400, 560
    img = Image.new('RGB', (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # "OP1" very large, centered
    title_font = get_font(180)
    center_text(draw, "OP1", title_font, 100, width, TEXT_COLOR)

    # Main tagline
    tagline_font = get_regular_font(48)
    center_text(draw, "AI-Powered Reply Marketing for Twitter/X", tagline_font, 320, width, GRAY_TEXT)

    # Sub-tagline
    sub_font = get_regular_font(28)
    center_text(draw, "Find conversations. Draft replies. Post from your browser.", sub_font, 390, width, DARK_GRAY)

    # Brand
    brand_font = get_font(20)
    center_text(draw, "OPERATIVE1", brand_font, 490, width, DARK_GRAY)

    # Save as PNG (24-bit, no alpha)
    path = os.path.join(DOWNLOADS, "marquee-1400x560.png")
    img.save(path, 'PNG')
    print(f"Created {path}")

    # Also save as JPEG
    jpeg_path = os.path.join(DOWNLOADS, "marquee-1400x560.jpg")
    img.save(jpeg_path, 'JPEG', quality=95)
    print(f"Created {jpeg_path}")

    return img


def main():
    os.makedirs(DOWNLOADS, exist_ok=True)

    print("Generating Chrome Web Store assets...")
    print()

    create_store_icon()
    create_promo_tile()
    create_marquee_tile()
    create_screenshot()

    print()
    print("All assets saved to ~/Downloads/")
    print()
    print("Files created:")
    print("  - store-icon-128.png (128x128)")
    print("  - promo-440x280.png (440x280)")
    print("  - marquee-1400x560.png (1400x560)")
    print("  - marquee-1400x560.jpg (1400x560)")
    print("  - screenshot-1280x800.png (1280x800)")


if __name__ == '__main__':
    main()
