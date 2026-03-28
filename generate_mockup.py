"""Generate a static mockup image of the overlay UI."""

from PIL import Image, ImageDraw, ImageFont
import os

WIDTH = 960
HEIGHT = 540

BG = (26, 26, 46)
PANEL_BG = (22, 33, 62)
ACCENT = (15, 52, 96)
HEADER_COLOR = (0, 210, 255)
TEXT = (224, 224, 224)
STAT_COLOR = (160, 160, 160)
BAR_BG = (42, 42, 74)

ACTION_COLORS = {
    "FOLD": (136, 136, 170),
    "CHECK": (136, 170, 204),
    "CALL": (136, 204, 170),
    "BET 75%": (204, 170, 136),
    "RAISE": (204, 204, 136),
    "ALL-IN": (204, 136, 170),
}


def draw_mockup():
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    # Try to use a monospace font
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 18)
        font_med = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 14)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 11)
    except Exception:
        font_big = ImageFont.load_default()
        font_med = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Top bar — game info
    draw.rectangle([(0, 0), (WIDTH, 40)], fill=ACCENT)
    draw.text(
        (15, 10),
        "FLOP  |  Board: Ah Kd 7c  |  Pot: 8.5BB  |  Hero: Qs Qd (CO)",
        fill=HEADER_COLOR, font=font_med,
    )

    # Divider
    mid_x = WIDTH // 2

    # Left panel — Exploitative
    draw.rectangle([(5, 48), (mid_x - 3, HEIGHT - 35)], fill=PANEL_BG, outline=(40, 50, 80))
    draw.text((15, 55), "EXPLOITATIVE", fill=HEADER_COLOR, font=font_big)

    # Opponent stats
    y = 85
    stats_lines = [
        "Villain: DonkOrleone",
        "VPIP: 38%  |  PFR: 12%  |  3Bet: 4%",
        "Fold to CB: 72%  |  AF: 1.2  |  Hands: 156",
        "",
        "=> Overfolds to cbet, passive preflop",
    ]
    for line in stats_lines:
        color = STAT_COLOR if not line.startswith("=>") else (255, 170, 0)
        draw.text((15, y), line, fill=color, font=font_small)
        y += 17

    # Exploitative strategy bars
    y += 10
    draw.text((15, y), "Strategy:", fill=TEXT, font=font_med)
    y += 25

    exploit_actions = [
        ("BET 75%", 0.82),
        ("CHECK", 0.18),
    ]
    _draw_action_bars(draw, 15, y, mid_x - 20, exploit_actions, font_med, font_small)

    # EV
    draw.text((15, HEIGHT - 70), "EV: +2.45 BB", fill=TEXT, font=font_med)

    # Right panel — GTO Pure
    draw.rectangle([(mid_x + 3, 48), (WIDTH - 5, HEIGHT - 35)], fill=PANEL_BG, outline=(40, 50, 80))
    rx = mid_x + 15
    draw.text((rx, 55), "GTO PURE", fill=HEADER_COLOR, font=font_big)

    # GTO strategy bars
    y = 145
    draw.text((rx, y), "Strategy:", fill=TEXT, font=font_med)
    y += 25

    gto_actions = [
        ("BET 75%", 0.55),
        ("CHECK", 0.45),
    ]
    _draw_action_bars(draw, rx, y, WIDTH - 20, gto_actions, font_med, font_small)

    # EV
    draw.text((rx, HEIGHT - 70), "EV: +1.82 BB", fill=TEXT, font=font_med)

    # Bottom status bar
    draw.rectangle([(0, HEIGHT - 30), (WIDTH, HEIGHT)], fill=ACCENT)
    draw.text((15, HEIGHT - 24), "Ready  |  D=Debug OCR  |  E=Toggle Exploit  |  Q=Quit", fill=STAT_COLOR, font=font_small)

    # Save
    out_path = "/home/user/inventive-ai/overlay_mockup.png"
    img.save(out_path)
    print(f"Mockup saved to {out_path}")
    return out_path


def _draw_action_bars(draw, x_start, y_start, x_end, actions, font_med, font_small):
    """Draw action frequency bars."""
    bar_width = (x_end - x_start) - 120
    y = y_start

    for action_name, freq in actions:
        color = ACTION_COLORS.get(action_name, TEXT)

        # Action label
        draw.text((x_start, y + 2), action_name, fill=color, font=font_med)

        # Bar background
        bar_x = x_start + 90
        bar_h = 20
        draw.rectangle([(bar_x, y), (bar_x + bar_width, y + bar_h)], fill=BAR_BG)

        # Bar fill
        fill_w = int(bar_width * freq)
        draw.rectangle([(bar_x, y), (bar_x + fill_w, y + bar_h)], fill=color)

        # Percentage
        pct_text = f"{freq * 100:.0f}%"
        draw.text((bar_x + bar_width + 8, y + 2), pct_text, fill=TEXT, font=font_med)

        y += 30


if __name__ == "__main__":
    draw_mockup()
