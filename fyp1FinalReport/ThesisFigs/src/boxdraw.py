"""Small helper for hand-placed box diagrams (layers, grids, file trees).

Figures are drawn at their final printed size (width ≤ 6 in ≈ 15 cm) so a font
size here is the printed size. Colours follow DIAGRAM_SPECS §0.3.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Ellipse, Rectangle  # noqa: E402

OUT = Path(__file__).resolve().parent.parent
INK, LINE, MUTED = "#1F2933", "#52606D", "#6B7785"
STYLE = {  # fill, border
    "A": ("#DCE9F7", "#2F6DB5"),
    "B": ("#DFF0E3", "#2E8B57"),
    "C": ("#FCE8D0", "#D9822B"),
    "D": ("#E9DFF2", "#7B4BA8"),
    "N": ("#F1F3F5", "#6B7785"),
    "R": ("#F8D7DA", "#C0392B"),
    "P": ("#FFFFFF", "#6B7785"),  # planned: dashed
    "W": ("#FFFFFF", "#52606D"),
}
BAND = {"A": "#F3F8FD", "B": "#F3FAF5", "C": "#FEF7EE", "D": "#F8F4FB", "N": "#F7F8F9"}
DASH = (0, (4, 2.5))
FS = 8.0


class Canvas:
    def __init__(self, w: float, h: float, font: float = FS):
        plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": font})
        self.fs = font
        self.fig = plt.figure(figsize=(w, h))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, w)
        self.ax.set_ylim(0, h)
        self.ax.axis("off")

    # ------------------------------------------------------------------ shapes
    def box(self, x, y, w, h, text, style="N", bold_first=True, fs=None, align="center",
            dashed=None, lw=1.1, z=3):
        fill, edge = STYLE[style]
        dashed = style == "P" if dashed is None else dashed
        self.ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.04",
                                         facecolor=fill, edgecolor=edge, linewidth=lw,
                                         linestyle=DASH if dashed else "-", zorder=z))
        self.text_in(x, y, w, h, text, bold_first=bold_first, fs=fs, align=align,
                     color=MUTED if style == "P" else INK, z=z + 1)
        return (x, y, w, h)

    def text_in(self, x, y, w, h, text, bold_first=True, fs=None, align="center", color=INK, z=4):
        fs = fs or self.fs
        lines = text.split("\n")
        n = len(lines)
        lh = fs / 72 * 1.22
        top = y + h / 2 + (n - 1) * lh / 2
        tx = {"center": x + w / 2, "left": x + 0.06}[align]
        for i, ln in enumerate(lines):
            self.ax.text(tx, top - i * lh, ln, ha=align, va="center", fontsize=fs, color=color,
                         fontweight="bold" if (bold_first and i == 0) else "normal", zorder=z)

    def band(self, x, y, w, h, label, style="N", label_w=0.32):
        self.ax.add_patch(Rectangle((x, y), w, h, facecolor=BAND.get(style, "#F7F8F9"),
                                    edgecolor=STYLE[style][1], linewidth=0.9, zorder=1))
        self.ax.add_patch(Rectangle((x, y), label_w, h, facecolor=STYLE[style][0],
                                    edgecolor=STYLE[style][1], linewidth=0.9, zorder=1))
        self.ax.text(x + label_w / 2, y + h / 2, label, rotation=90, ha="center", va="center",
                     fontsize=self.fs - 0.4, fontweight="bold", zorder=2)

    def cylinder(self, x, y, w, h, text, style="B", fs=None):
        fill, edge = STYLE[style]
        e = min(0.09, h * 0.18)
        self.ax.add_patch(Rectangle((x, y + e / 2), w, h - e, facecolor=fill, edgecolor="none", zorder=3))
        self.ax.plot([x, x], [y + e / 2, y + h - e / 2], color=edge, lw=1.1, zorder=4)
        self.ax.plot([x + w, x + w], [y + e / 2, y + h - e / 2], color=edge, lw=1.1, zorder=4)
        self.ax.add_patch(Ellipse((x + w / 2, y + e / 2), w, e, facecolor=fill, edgecolor=edge, lw=1.1, zorder=3))
        self.ax.add_patch(Ellipse((x + w / 2, y + h - e / 2), w, e, facecolor=fill, edgecolor=edge, lw=1.1, zorder=5))
        self.text_in(x, y - e / 4, w, h, text, bold_first=False, fs=fs, z=6)
        return (x, y, w, h)

    # ------------------------------------------------------------------ links
    def arrow(self, p, q, label=None, label_at=None, style="-|>", dashed=False, color=LINE,
              fs=None, ha="left", rad=0.0, lw=1.0):
        self.ax.annotate("", xy=q, xytext=p, zorder=6,
                         arrowprops=dict(arrowstyle=style, color=color, lw=lw, shrinkA=0, shrinkB=0,
                                         linestyle=DASH if dashed else "-",
                                         connectionstyle=f"arc3,rad={rad}"))
        if label:
            lx, ly = label_at or ((p[0] + q[0]) / 2 + 0.05, (p[1] + q[1]) / 2)
            self.ax.text(lx, ly, label, ha=ha, va="center", fontsize=(fs or self.fs) - 0.6,
                         color=INK, zorder=7, linespacing=1.15,
                         bbox=dict(facecolor="white", edgecolor="none", pad=0.4, alpha=0.9))

    def note(self, x, y, text, fs=None, ha="left", color=MUTED, va="center", weight="normal"):
        self.ax.text(x, y, text, ha=ha, va=va, fontsize=fs or self.fs - 0.6, color=color,
                     linespacing=1.2, fontweight=weight, zorder=7)

    def save(self, name):
        self.fig.savefig(OUT / f"{name}.png", dpi=300, facecolor="white")
        plt.close(self.fig)
        print("wrote", name)


# helpers for box geometry
def top(b):
    return (b[0] + b[2] / 2, b[1] + b[3])


def bottom(b):
    return (b[0] + b[2] / 2, b[1])


def left(b):
    return (b[0], b[1] + b[3] / 2)


def right(b):
    return (b[0] + b[2], b[1] + b[3] / 2)


def node(c: Canvas, x, y, w, h, title, style="N", d=0.07, dashed=False):
    """UML deployment node: a box with a 3D top/right face and a title strip."""
    import matplotlib.patches as mp

    fill, edge = STYLE[style]
    ls = DASH if dashed else "-"
    c.ax.add_patch(mp.Polygon([(x, y + h), (x + d, y + h + d), (x + w + d, y + h + d), (x + w, y + h)],
                              closed=True, facecolor=fill, edgecolor=edge, lw=1.0, linestyle=ls, zorder=1))
    c.ax.add_patch(mp.Polygon([(x + w, y), (x + w + d, y + d), (x + w + d, y + h + d), (x + w, y + h)],
                              closed=True, facecolor=fill, edgecolor=edge, lw=1.0, linestyle=ls, zorder=1))
    c.ax.add_patch(mp.Rectangle((x, y), w, h, facecolor=BAND.get(style, "#FFFFFF") if style != "P" else "white",
                                edgecolor=edge, lw=1.1, linestyle=ls, zorder=1))
    lines = title.split("\n")
    for i, ln in enumerate(lines):
        c.ax.text(x + w / 2, y + h - 0.12 - i * c.fs / 72 * 1.22, ln, ha="center", va="center",
                  fontsize=c.fs - (0.8 if ln.startswith("«") else 0),
                  fontweight="normal" if ln.startswith("«") else "bold",
                  style="italic" if ln.startswith("«") else "normal",
                  color=MUTED if dashed else INK, zorder=2)
    return (x, y, w, h)
