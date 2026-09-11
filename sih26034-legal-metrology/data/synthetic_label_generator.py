"""
Generates synthetic packaged-commodity label images with known ground-truth
declarations, deliberately injecting violations (missing MRP, tiny font,
missing date, etc.) into a fraction of them.

Use this to build a labeled test set quickly instead of waiting on
scraping/licensing for a real dataset.

Usage:
    python synthetic_label_generator.py --count 50 --out ./synthetic_labels
"""
import argparse
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MANUFACTURERS = [
    "ABC Foods Pvt Ltd, 123 MG Road, Bengaluru 560001",
    "Sunrise Snacks Ltd, Plot 45 Industrial Area, Pune 411001",
    "Green Valley Dairy, Sector 12, Gurugram 122001",
    "National Spices Co., 88 Anna Salai, Chennai 600002",
]
PRODUCTS = ["Masala Chips", "Toned Milk", "Turmeric Powder", "Instant Noodles", "Cooking Oil"]
NET_QTY_OPTIONS = [("100", "g"), ("200", "g"), ("500", "g"), ("1", "kg"), ("500", "ml"), ("1", "l")]


def build_label_text(violate: dict) -> list[str]:
    """Returns list of lines to render; `violate` flags which declarations to omit/break."""
    mfr = random.choice(MANUFACTURERS)
    product = random.choice(PRODUCTS)
    qty_val, qty_unit = random.choice(NET_QTY_OPTIONS)
    mrp = random.randint(20, 500)
    month = random.randint(1, 12)
    year = random.choice([2025, 2026])

    lines = [product]

    if not violate.get("missing_address"):
        lines.append(f"Mfd by {mfr}")

    if not violate.get("missing_net_qty"):
        lines.append(f"Net Wt: {qty_val}{qty_unit}")

    if not violate.get("missing_mrp"):
        tax_wording = "" if violate.get("mrp_no_tax_wording") else " incl. of all taxes"
        lines.append(f"MRP: Rs.{mrp}{tax_wording}")

    if not violate.get("missing_date"):
        lines.append(f"Mfg Date: {month:02d}/{year}")

    if not violate.get("missing_consumer_care"):
        lines.append("Consumer Care: 1800-123-4567")

    return lines


def render_label(lines: list[str], out_path: Path, tiny_font: bool = False):
    width, height = 600, 400
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    try:
        font_size = 10 if tiny_font else 18
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    y = 20
    for line in lines:
        draw.text((20, y), line, fill="black", font=font)
        y += (font_size if tiny_font else 18) + 12

    img.save(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--out", type=str, default="./synthetic_labels")
    parser.add_argument("--violation-rate", type=float, default=0.4, help="Fraction of labels with an injected violation")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    ground_truth = []

    violation_types = [
        {"missing_address": True},
        {"missing_net_qty": True},
        {"missing_mrp": True},
        {"missing_date": True},
        {"missing_consumer_care": True},
        {"mrp_no_tax_wording": True},
        {"tiny_font": True},
    ]

    for i in range(args.count):
        violate = {}
        should_violate = random.random() < args.violation_rate
        if should_violate:
            violate = dict(random.choice(violation_types))

        lines = build_label_text(violate)
        filename = f"label_{i:03d}.png"
        render_label(lines, out_dir / filename, tiny_font=violate.get("tiny_font", False))

        ground_truth.append({
            "file": filename,
            "expected_status": "FAIL" if should_violate else "PASS",
            "injected_violation": violate if should_violate else None,
            "rendered_lines": lines,
        })

    with open(out_dir / "ground_truth.json", "w") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Generated {args.count} synthetic labels in {out_dir}")
    print(f"Ground truth written to {out_dir / 'ground_truth.json'}")


if __name__ == "__main__":
    main()
