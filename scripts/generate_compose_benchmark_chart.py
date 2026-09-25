"""Render the dated local Compose benchmark chart from recorded evidence."""

from pathlib import Path

import matplotlib.pyplot as plt


NAVY = "#003366"
BLUE = "#006699"
TEAL = "#4A90A4"
LIGHT = "#E8F0F5"
GREEN = "#2E8B57"

OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "assets" / "compose-benchmark-2026-09-24.png"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(1, 3, figsize=(12, 3.6), facecolor="white")
    metrics = [
        ("Throughput", 61.89, "requests/s", BLUE),
        ("Latency", 147.95, "p95 ms", TEAL),
        ("Errors", 0, "of 48 requests", GREEN),
    ]

    for axis, (title, value, unit, color) in zip(axes, metrics, strict=True):
        axis.set_facecolor(LIGHT)
        axis.text(0.5, 0.70, title, ha="center", va="center", color=NAVY, fontsize=13, fontweight="bold")
        axis.text(0.5, 0.45, f"{value:g}", ha="center", va="center", color=color, fontsize=31, fontweight="bold")
        axis.text(0.5, 0.22, unit, ha="center", va="center", color=NAVY, fontsize=11)
        axis.set_xticks([])
        axis.set_yticks([])
        for spine in axis.spines.values():
            spine.set_visible(False)

    figure.suptitle("Local Docker Compose benchmark · 2026-09-24", color=NAVY, fontsize=16, fontweight="bold", y=1.02)
    figure.text(0.5, -0.02, "48 unique requests · concurrency 6 · two Redis Streams workers · p50 56.88 ms · final queue lag 0", ha="center", color=NAVY, fontsize=10)
    figure.tight_layout()
    figure.savefig(OUTPUT, dpi=200, bbox_inches="tight", facecolor="white")


if __name__ == "__main__":
    main()
