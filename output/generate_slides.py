#!/usr/bin/env python3
"""Generate slide images for the Dating Advice video.

Dark/moody aesthetic faceless YouTube video.
Each slide is a 1920x1080 PNG timed to transcript segments.
"""

from PIL import Image, ImageDraw, ImageFont
import os
import json

# === DIMENSIONS ===
W, H = 1920, 1080
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "slides")

# === COLORS (no # prefix) ===
BG = (13, 13, 13)
BG_PANEL = (22, 22, 37)
BG_DARK = (8, 8, 8)
TEXT = (240, 240, 240)
TEXT_DIM = (160, 165, 180)
TEXT_MUTED = (100, 108, 130)
RED = (255, 59, 59)
DARK_RED = (140, 30, 30)
AMBER = (246, 173, 85)
BORDER = (40, 40, 60)

# === FONTS ===
FD = "C:/Windows/Fonts"

def _f(name, size):
    paths = {
        "impact": f"{FD}/impact.ttf",
        "ariblk": f"{FD}/ariblk.ttf",
        "arialbd": f"{FD}/arialbd.ttf",
        "arial": f"{FD}/arial.ttf",
        "segoe": f"{FD}/segoeui.ttf",
        "segoeb": f"{FD}/segoeuib.ttf",
    }
    return ImageFont.truetype(paths[name], size)

# Pre-load common fonts
F = {
    "impact_hero": _f("impact", 144),
    "impact_lg": _f("impact", 84),
    "impact_md": _f("impact", 68),
    "ariblk_lg": _f("ariblk", 56),
    "ariblk_md": _f("ariblk", 46),
    "arialbd_xl": _f("arialbd", 60),
    "arialbd_lg": _f("arialbd", 50),
    "arialbd_md": _f("arialbd", 40),
    "arialbd_sm": _f("arialbd", 32),
    "arial_lg": _f("arial", 40),
    "arial_md": _f("arial", 34),
    "arial_sm": _f("arial", 26),
    "segoe_md": _f("segoe", 28),
    "segoe_sm": _f("segoe", 22),
    "segoeb_md": _f("segoeb", 26),
    "segoeb_sm": _f("segoeb", 20),
}


# === HELPERS ===

def new_img():
    return Image.new("RGB", (W, H), BG)


def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def center_x(draw, text, font):
    tw, _ = text_size(draw, text, font)
    return (W - tw) // 2


def draw_centered(draw, text, y, font, color=TEXT):
    x = center_x(draw, text, font)
    draw.text((x, y), text, fill=color, font=font)
    _, th = text_size(draw, text, font)
    return y + th


def draw_multiline_centered(draw, text, y, font, color=TEXT, spacing=12):
    for line in text.split("\n"):
        y = draw_centered(draw, line, y, font, color) + spacing
    return y


def draw_x_mark(draw, cx, cy, size, color=RED, width=10):
    s = size // 2
    draw.line([(cx - s, cy - s), (cx + s, cy + s)], fill=color, width=width)
    draw.line([(cx - s, cy + s), (cx + s, cy - s)], fill=color, width=width)


def draw_strikethrough(draw, text, x, y, font, text_color=TEXT, strike_color=RED):
    draw.text((x, y), text, fill=text_color, font=font)
    tw, th = text_size(draw, text, font)
    mid_y = y + th // 2
    draw.line([(x - 5, mid_y), (x + tw + 5, mid_y)], fill=strike_color, width=4)


def add_vignette(img, strength=60):
    """Add a subtle dark vignette around edges."""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    # Draw concentric semi-transparent rectangles around edges
    for i in range(strength):
        alpha = int((strength - i) * 2.5)
        if alpha > 255:
            alpha = 255
        d.rectangle([(i, i), (W - i, H - i)], outline=(0, 0, 0, alpha))
    img_rgba = img.convert("RGBA")
    img_rgba = Image.alpha_composite(img_rgba, overlay)
    return img_rgba.convert("RGB")


def draw_panel(draw, x1, y1, x2, y2, fill=BG_PANEL, border_color=BORDER, radius=12):
    draw.rounded_rectangle([(x1, y1), (x2, y2)], radius=radius, fill=fill)
    draw.rounded_rectangle([(x1, y1), (x2, y2)], radius=radius, outline=border_color, width=1)


# === SLIDE GENERATORS ===

def gen_intro():
    """Slide 1: 'Here's what the internet has taught me about dating'"""
    img = new_img()
    draw = ImageDraw.Draw(img)

    # Subtle phone glow in center background
    for i in range(80, 0, -1):
        alpha_r = int(i * 0.4)
        c = (10 + alpha_r // 8, 12 + alpha_r // 6, 30 + alpha_r // 3)
        draw.rounded_rectangle(
            [(W // 2 - 180 - i, 180 - i), (W // 2 + 180 + i, 820 + i)],
            radius=20 + i // 4, fill=c
        )

    # Phone outline
    draw.rounded_rectangle(
        [(W // 2 - 180, 180), (W // 2 + 180, 820)],
        radius=20, outline=(30, 35, 60), width=2
    )

    # Main text
    draw_multiline_centered(
        draw,
        "Here's what the internet\nhas taught me\nabout dating.",
        360, F["arialbd_xl"], TEXT
    )

    img = add_vignette(img, 50)
    return img


def gen_beat():
    """Slide 2: Silence/tension — near-black."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Three subtle dots
    dot_y = H // 2
    for i, dx in enumerate([-40, 0, 40]):
        brightness = 30 + i * 8
        draw.ellipse(
            [(W // 2 + dx - 4, dot_y - 4), (W // 2 + dx + 4, dot_y + 4)],
            fill=(brightness, brightness, brightness + 5)
        )
    return img


def gen_dont_impact():
    """Slide 3: 'DON'T.' — massive red text."""
    img = new_img()
    draw = ImageDraw.Draw(img)

    # Large radial glow behind text
    for i in range(80, 0, -1):
        c = (20 + i, 3 + i // 10, 3 + i // 10)
        draw.rounded_rectangle(
            [(W // 2 - 350 - i, H // 2 - 120 - i),
             (W // 2 + 350 + i, H // 2 + 120 + i)],
            radius=15, fill=c
        )

    draw_centered(draw, "DON'T.", H // 2 - 80, F["impact_hero"], RED)

    img = add_vignette(img, 40)
    return img


def gen_dont_card(dont_text, reason_text, card_num):
    """Generic 'don't' card: red accent bar + X + text on dark panel."""
    img = new_img()
    draw = ImageDraw.Draw(img)

    # Panel
    px1, py1, px2, py2 = 240, 220, 1680, 860
    draw_panel(draw, px1, py1, px2, py2)

    # Red accent bar on left
    draw.rectangle([(px1, py1 + 12), (px1 + 6, py2 - 12)], fill=RED)

    # Large faded X in background — far left, very dim, won't overlap text
    draw_x_mark(draw, 320, (py1 + py2) // 2, 280, color=(30, 10, 10), width=20)

    # Small red X icon — positioned to left of text
    draw_x_mark(draw, 340, py1 + 160, 50, RED, 8)

    # Don't text — starts well to the right of the X
    y = py1 + 100
    for line in dont_text.split("\n"):
        draw.text((440, y), line, fill=TEXT, font=F["ariblk_lg"])
        _, th = text_size(draw, line, F["ariblk_lg"])
        y += th + 8

    # Reason text — with more spacing from dont text
    y += 40
    for line in reason_text.split("\n"):
        draw.text((440, y), line, fill=TEXT_MUTED, font=F["arial_md"])
        _, th = text_size(draw, line, F["arial_md"])
        y += th + 6

    # Card number indicator
    draw.text((1600, py2 - 50), str(card_num), fill=BORDER, font=F["segoeb_sm"])

    img = add_vignette(img, 30)
    return img


def gen_punchline(main_text, sub_text=None):
    """Stark punchline text on black."""
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    y = draw_multiline_centered(draw, main_text, 360, F["arialbd_xl"], TEXT)

    if sub_text:
        draw_multiline_centered(draw, sub_text, y + 30, F["arial_md"], TEXT_DIM)

    return img


def gen_transition(main_text, sub_text=None):
    """Section transition slide with amber accent."""
    img = new_img()
    draw = ImageDraw.Draw(img)

    # Amber accent line
    line_w = 120
    draw.line(
        [(W // 2 - line_w, H // 2 - 80), (W // 2 + line_w, H // 2 - 80)],
        fill=AMBER, width=3
    )

    y = draw_multiline_centered(draw, main_text, H // 2 - 40, F["arialbd_xl"], AMBER)

    if sub_text:
        draw_multiline_centered(draw, sub_text, y + 20, F["arial_md"], TEXT_MUTED)

    img = add_vignette(img, 40)
    return img


def gen_accusation(topic, labels, sub=None):
    """Accusation slide: topic + red label badges."""
    img = new_img()
    draw = ImageDraw.Draw(img)

    # Topic text
    y = draw_multiline_centered(draw, topic, 240, F["arialbd_lg"], TEXT)

    # Subtitle
    if sub:
        y = draw_multiline_centered(draw, sub, y + 20, F["arial_sm"], TEXT_MUTED)

    # Red label badges
    y += 50
    for label in labels:
        tw, th = text_size(draw, label, F["ariblk_md"])
        x = (W - tw) // 2
        # Badge background
        pad_x, pad_y = 40, 14
        draw.rounded_rectangle(
            [(x - pad_x, y - pad_y), (x + tw + pad_x, y + th + pad_y)],
            radius=8, fill=DARK_RED
        )
        draw.rounded_rectangle(
            [(x - pad_x, y - pad_y), (x + tw + pad_x, y + th + pad_y)],
            radius=8, outline=RED, width=1
        )
        draw.text((x, y), label, fill=TEXT, font=F["ariblk_md"])
        y += th + pad_y * 2 + 20

    img = add_vignette(img, 30)
    return img


def gen_attraction(attracted_to, judgment):
    """'Attracted to X -> That's Y' slide."""
    img = new_img()
    draw = ImageDraw.Draw(img)

    # Small label
    draw_centered(draw, "Being attracted to...", 250, F["segoe_md"], TEXT_MUTED)

    # The attribute
    draw_centered(draw, attracted_to, 320, F["arialbd_xl"], TEXT)

    # Down arrow
    arrow_y = 430
    cx = W // 2
    draw.polygon(
        [(cx - 15, arrow_y), (cx + 15, arrow_y), (cx, arrow_y + 25)],
        fill=AMBER
    )

    # Judgment in red — large, dramatic
    jy = 520
    draw_centered(draw, judgment.upper(), jy, F["impact_lg"], RED)

    # Red underline
    tw, th = text_size(draw, judgment.upper(), F["impact_lg"])
    ux = (W - tw) // 2
    draw.line(
        [(ux, jy + th + 8), (ux + tw, jy + th + 8)],
        fill=RED, width=4
    )

    img = add_vignette(img, 30)
    return img


def gen_attraction_special(attracted_to, sub_text):
    """Special 'attracted to mind' slide with '???' and commentary."""
    img = new_img()
    draw = ImageDraw.Draw(img)

    draw_centered(draw, "Being attracted to...", 220, F["segoe_md"], TEXT_MUTED)
    draw_centered(draw, attracted_to, 290, F["arialbd_xl"], TEXT)

    # Down arrow
    cx = W // 2
    draw.polygon(
        [(cx - 15, 400), (cx + 15, 400), (cx, 425)],
        fill=AMBER
    )

    # Question marks (uncertain)
    draw_centered(draw, "? ? ?", 480, F["impact_lg"], (60, 60, 80))

    # Commentary
    draw_multiline_centered(draw, sub_text, 620, F["arial_md"], TEXT_DIM)

    img = add_vignette(img, 30)
    return img


def gen_behavior(behavior, judgment):
    """'Wanting X makes you Y' behavior slide."""
    img = new_img()
    draw = ImageDraw.Draw(img)

    # Behavior text — centered, white
    draw_centered(draw, behavior, 320, F["arialbd_lg"], TEXT)

    # "makes you" connector
    draw_centered(draw, "makes you", 420, F["segoe_md"], TEXT_MUTED)

    # Judgment — huge red impact font, with breathing room
    draw_centered(draw, judgment.upper(), 510, F["impact_lg"], RED)

    img = add_vignette(img, 30)
    return img


def gen_finale():
    """Finale: Venn diagram with a single pixel of overlap."""
    img = new_img()
    draw = ImageDraw.Draw(img)

    # Title
    draw_centered(draw, "All acceptable romantic behavior", 80, F["arialbd_md"], TEXT_MUTED)

    # Venn diagram
    cy = 420
    r = 230
    left_cx = W // 2 - 170
    right_cx = W // 2 + 170

    # Fill circles with subtle semi-transparent color
    # Left circle
    draw.ellipse(
        [(left_cx - r, cy - r), (left_cx + r, cy + r)],
        fill=(25, 25, 50), outline=(70, 70, 110), width=3
    )
    # Right circle
    draw.ellipse(
        [(right_cx - r, cy - r), (right_cx + r, cy + r)],
        fill=(50, 20, 20), outline=(110, 60, 60), width=3
    )

    # Labels inside circles
    draw.text((left_cx - 100, cy - 30), "What you\nwant to do", fill=TEXT_DIM, font=F["segoeb_md"])
    draw.text((right_cx - 65, cy - 30), "What's\nacceptable", fill=TEXT_DIM, font=F["segoeb_md"])

    # THE PIXEL — small glowing dot at center (visible but still tiny for the joke)
    cx = W // 2
    # Glow rings — wider for visibility
    for i in range(20, 0, -1):
        brightness = max(0, 100 - i * 5)
        c = (255, min(59 + brightness, 180), min(59 + brightness, 120))
        draw.ellipse(
            [(cx - i, cy - i), (cx + i, cy + i)],
            fill=c if i < 6 else None,
            outline=c
        )
    # Core pixel — slightly bigger
    draw.ellipse([(cx - 5, cy - 5), (cx + 5, cy + 5)], fill=RED)

    # Arrow pointing to it
    draw.line([(cx + 30, cy - 50), (cx + 8, cy - 8)], fill=AMBER, width=2)
    draw.text((cx + 35, cy - 65), "the overlap", fill=AMBER, font=F["segoeb_sm"])

    # Final punchline text
    draw_multiline_centered(
        draw,
        "The overlap would be a single pixel,\nand it would probably still\nmake someone uncomfortable.",
        720, F["arial_md"], TEXT_DIM
    )

    img = add_vignette(img, 40)
    return img


# === SCENE DATA ===
# (filename, start_sec, end_sec, generator_func)

def build_all_slides():
    scenes = []

    # --- INTRO ---
    scenes.append(("slide_01_intro.png", 14.83, 18.41, gen_intro))

    # --- BEAT ---
    scenes.append(("slide_02_beat.png", 18.41, 23.08, gen_beat))

    # --- DON'T ---
    scenes.append(("slide_03_dont.png", 23.08, 23.66, gen_dont_impact))

    # --- DON'T CARDS ---
    dont_cards = [
        ("slide_04_friends.png", 23.66, 26.02,
         "Don't date your friends.", "You'll ruin the friendship."),
        ("slide_05_online.png", 26.56, 30.62,
         "Don't date online.", "It's a toxic wasteland full of\nnarcissists and liars."),
        ("slide_06_coworkers.png", 31.32, 35.1,
         "Don't ask out co-workers.", "That's a harassment complaint\nwaiting to happen."),
        ("slide_07_strangers.png", 35.7, 38.16,
         "Don't approach strangers.", "What are you, a predator?"),
        ("slide_08_gym.png", 38.78, 41.6,
         "Don't flirt at the gym.", "People are there to work out."),
        ("slide_09_bars.png", 41.98, 45.0,
         "Don't talk to anyone at bars.", "They're just there for a drink."),
        ("slide_10_dms.png", 45.38, 47.76,
         "Don't slide into the DMs.", "That's desperate."),
        ("slide_11_organic.png", 48.08, 55.82,
         "Don't just wait for something\nto happen organically.",
         "That's passive and\nemotionally avoidant."),
    ]
    for i, (fname, start, end, dont, reason) in enumerate(dont_cards, 1):
        scenes.append((fname, start, end,
                        lambda d=dont, r=reason, n=i: gen_dont_card(d, r, n)))

    # --- PUNCHLINE 1 ---
    scenes.append(("slide_12_alone.png", 58.6, 61.94,
                    lambda: gen_punchline(
                        "Alone, I guess.",
                        "But at least you'll be morally clean.")))

    # --- TRANSITION 1 ---
    scenes.append(("slide_13_notdone.png", 62.36, 63.48,
                    lambda: gen_transition("You think I'm done?")))

    # --- ACCUSATIONS ---
    scenes.append(("slide_14_agegaps.png", 64.28, 69.54,
                    lambda: gen_accusation(
                        "Age gaps between\nconsenting adults",
                        ["Suspicious", "Diabolical"])))

    scenes.append(("slide_15_power.png", 70.08, 78.14,
                    lambda: gen_accusation(
                        "Power differences of any kind",
                        ["Automatically predatory"],
                        "Money, status, career, security,\nsocial confidence")))

    # --- ATTRACTIONS ---
    scenes.append(("slide_16_success.png", 78.14, 81.62,
                    lambda: gen_attraction("Someone's success", "Gold digging")))
    scenes.append(("slide_17_youth.png", 82.0, 84.46,
                    lambda: gen_attraction("Someone's youth", "Creepy")))
    scenes.append(("slide_18_looks.png", 85.04, 87.36,
                    lambda: gen_attraction("Someone's looks", "Objectifying")))

    scenes.append(("slide_19_mind.png", 88.22, 98.3,
                    lambda: gen_attraction_special(
                        "Someone's mind",
                        "Give it time.\nSomeone will make the argument.")))

    # --- TRANSITION 2 ---
    scenes.append(("slide_20_notdone2.png", 99.18, 102.84,
                    lambda: gen_transition(
                        "You think we're done here?",
                        "Oh, no, no, no, no.")))

    # --- BEHAVIORS ---
    behaviors = [
        ("slide_21_sex.png", 102.84, 104.5, "Wanting sex", "Shallow"),
        ("slide_22_commitment.png", 105.02, 106.8, "Wanting commitment", "Controlling"),
        ("slide_23_exclusivity.png", 106.8, 109.72, "Wanting exclusivity", "Insecure"),
        ("slide_24_open.png", 110.34, 112.94, "Open relationship", "Avoidant"),
        ("slide_25_likemore.png", 113.18, 115.56, "Liking someone more", "Pathetic"),
        ("slide_26_likeless.png", 116.26, 117.84, "Liking someone less", "Cruel"),
        ("slide_27_tryagain.png", 118.46, 120.88, "Trying again after rejection", "Disrespectful"),
        ("slide_28_walkaway.png", 121.8, 124.92, "Walking away too quickly", "Unavailable"),
        ("slide_29_tooearly.png", 125.86, 128.42, "Expressing interest too early", "Love bombing"),
        ("slide_30_toolate.png", 128.92, 132.04, "Expressing interest too late", "Breadcrumbing"),
    ]
    for fname, start, end, beh, judg in behaviors:
        scenes.append((fname, start, end,
                        lambda b=beh, j=judg: gen_behavior(b, j)))

    # --- FINALE ---
    scenes.append(("slide_31_finale.png", 135.34, 145.5, gen_finale))

    return scenes


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    scenes = build_all_slides()
    timing_data = []

    for fname, start, end, gen_func in scenes:
        img = gen_func()
        path = os.path.join(OUTPUT_DIR, fname)
        img.save(path, "PNG")
        timing_data.append({
            "filename": fname,
            "start": start,
            "end": end,
            "duration": round(end - start, 3)
        })
        print(f"  {fname}  ({end - start:.2f}s)")

    # Save timing data as JSON for DaVinci Resolve import
    timing_path = os.path.join(OUTPUT_DIR, "timings.json")
    with open(timing_path, "w") as f:
        json.dump(timing_data, f, indent=2)

    print(f"\nGenerated {len(scenes)} slides -> {OUTPUT_DIR}")
    print(f"Timing data -> {timing_path}")


if __name__ == "__main__":
    main()
