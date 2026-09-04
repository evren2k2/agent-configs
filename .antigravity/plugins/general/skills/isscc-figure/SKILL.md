---
name: isscc-figure
description: Fix and format matplotlib figures to ISSCC/IEEE publication standards. Use when asked to "format this figure", "make this publication-quality", "fix the figure style", or when reviewing figures for paper submission.
---

# ISSCC Figure Formatter

Apply this to every matplotlib figure headed for a paper. The preamble is the spec —
copy it verbatim; the rules after it cover what a helper cannot set for you.

## Preamble (copy verbatim)

```python
CLR_NAVY   = "#1a1f7a"   # primary
CLR_RED    = "#C0392B"   # secondary
CLR_GREEN  = "#27AE60"   # tertiary   — third curve in 3+ curve panels
CLR_PURPLE = "#8E44AD"   # quaternary — twin axis or fourth curve

_ISSCC_FONT_LOADED = False
try:
    _fm = matplotlib.font_manager.FontManager()
    _arial_narrow_paths = [f.fname for f in _fm.ttflist if "Arial Narrow" in f.name]
    if _arial_narrow_paths:
        matplotlib.font_manager.fontManager.addfont(_arial_narrow_paths[0])
        plt.rcParams["font.family"] = "Arial Narrow"
        _ISSCC_FONT_LOADED = True
except Exception:
    pass
if not _ISSCC_FONT_LOADED:
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.weight"] = "bold"

# Bare $x$ math inherits the body font; keep the default `dejavusans` fontset so
# \mathbf / \hat render sans-serif (matching the body). Never set mathtext.fontset.
plt.rcParams["mathtext.default"] = "regular"


def apply_isscc_style(ax):
    ax.spines["top"].set_linewidth(0)
    ax.spines["right"].set_linewidth(0)
    ax.spines["left"].set_linewidth(2.0)
    ax.spines["bottom"].set_linewidth(2.0)
    ax.tick_params(axis="both", which="major", labelsize=22, width=2)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontweight("bold")
    ax.patch.set_facecolor("none")


def _save_fig(fig, out_base):
    for ext in ("png", "svg", "eps"):        # all three, every time
        fig.savefig(f"{out_base}.{ext}", transparent=True, bbox_inches="tight")
    plt.close(fig)
```

## Every figure

- `apply_isscc_style(ax)` on **every** axes, plus `fig.patch.set_facecolor("none")`
- Axis labels `fontsize=24, weight="bold"`, black — unless the axis carries one
  dedicated curve (twin axis, single-curve panel), then color it to match that curve
- Legend `prop={"size": 18, "weight": "bold"}`, `framealpha=0.7`
- Markers `markersize=10, markerfacecolor="white", markeredgewidth=2.5`
- Lines `linewidth=3` for data, `2–2.5` for reference / dashed
- Save through `_save_fig`: PNG + SVG + EPS, transparent. Never `facecolor="white"`,
  never PNG alone

| Layout | `figsize` (all at `dpi=300`) |
|--------|------------------------------|
| Single | `(6, 6)` |
| 1x2 | `(12, 6)` |
| 2x1 | `(8, 10)` |
| 2x2 | `(12, 10)` |

## Off unless justified

- **Grid** — only where reference lines are genuinely required, e.g. a log-log
  convergence sweep. Never as decoration on a clean line plot.
- **Panel titles** — only when a multi-panel figure truly needs labels; then
  `fontsize=22, weight="bold", pad=12` with `"(a)  "` / `"(b)  "` prefixes.
- **`plt.show()`** — only behind a `--no-show` gate.
- **Default matplotlib colors** — never; use the four above.

## Domain axes

| Axis | Label | Scale |
|------|-------|-------|
| Azimuth | `"$\\phi$ (deg)"` | Linear, −90 to 90 |
| SINR | `"SINR (dB)"` | Linear |
| BER | `"BER"` | Log (semilogy) |
| Tracking error | `"Tracking Error (deg)"` | Linear/log |
| Beam pattern | `"Normalized Pattern (dB)"` | Linear, −60 to 0 |
| Eigenvalue | `r"eigenvalue  $\\lambda_k$"` | Log |
| Iterations | `"# of Iterations"` | Linear or log |

## Twin axis

When each axis carries one dedicated curve, color its **spine + tick marks + tick
labels + ylabel** to match that curve so the reader can pair data with axis at a
glance. `apply_isscc_style` the left axis as usual, then style the right one manually:

```python
ax1.spines["left"].set_color(CLR_NAVY)
ax1.tick_params(axis="y", which="major", labelsize=22, width=2, colors=CLR_NAVY)
for label in ax1.get_yticklabels():
    label.set_color(CLR_NAVY)
    label.set_fontweight("bold")
ax1.set_ylabel(..., fontsize=24, color=CLR_NAVY, weight="bold")

ax2 = ax1.twinx()
ax2.spines["top"].set_linewidth(0)
ax2.spines["left"].set_linewidth(0)
ax2.spines["right"].set_linewidth(2.0)
ax2.spines["right"].set_color(CLR_PURPLE)
ax2.tick_params(axis="y", which="major", labelsize=22, width=2, colors=CLR_PURPLE)
for label in ax2.get_yticklabels():
    label.set_fontweight("bold")
ax2.set_ylabel(..., fontsize=24, color=CLR_PURPLE, weight="bold")
ax2.patch.set_facecolor("none")
```

## Reference / regime-boundary lines

Stability bounds, asymptotes and "ideal" levels get a thin dashed line plus a rotated
label. Place the label at the *geometric* mean of the data range on a log axis, the
arithmetic mean on a linear one, so it stays inside the plot box:

```python
ax.axvline(GB_STABILITY, color=CLR_RED, linewidth=2.0, linestyle="--", alpha=0.85)
y_text = np.sqrt(residuals.min() * residuals.max())   # log axis
ax.text(GB_STABILITY * 0.93, y_text,
        rf"unstable ($\gamma\bar{{\beta}}\geq{GB_STABILITY:.0f}$)",
        color=CLR_RED, fontsize=18, fontweight="bold",
        rotation=90, va="center", ha="right")
```

Nudge the label off the line with `0.93 * x_ref` (log) or `x_ref - small_offset` (linear).

## Subscripts: no `\mathrm{}` for text

With `mathtext.default = "regular"`, bare text inside `$...$` inherits Arial Narrow.
`\mathrm{}` reverts it to DejaVu Sans, and the mismatch is visible.

```python
ax.set_ylabel(r"$T_{\mathrm{update}} / T_{\mathrm{MIN}}$")   # wrong — DejaVu Sans
ax.set_ylabel(r"$T_{update} / T_{MIN}$")                     # correct
```

Reserve `\mathrm{}` for genuine math-mode roman (`\mathrm{d}x`). Applies to
`set_xlabel`, `set_ylabel`, `ax.text()`, legend labels and annotations alike.

## Common fixes

- **Tick overlap** — `ax.xaxis.set_major_locator(plt.MaxNLocator(nbins=6))`, or `rotation=45`
- **Legend clipping** — reposition with `loc=...`; `frameon=False` if the frame still clutters
- **Inconsistent spines** — `for ax in fig.axes: apply_isscc_style(ax)`
- **Suptitle overlap** — `fig.tight_layout(rect=[0, 0, 1, 0.95])`
