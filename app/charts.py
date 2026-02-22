"""
NeuraDeck Universal Business Charts
===================================
Four matplotlib charts for ANY company: Revenue, Sales Funnel, Team Growth, Market Opportunity.
Colors: steel blue bars, gold labels, navy accents.
"""

from pathlib import Path
from typing import Any, Dict, List
import numpy as np # type: ignore[reportMissingImports]

# Theme
NAVY = "#0A0F1E"
NAVY_LIGHT = "#1A1F2E"
STEEL_BLUE = "#4682B4"
GOLD = "#D4AF37"
GOLD_LIGHT = "#F4E4BC"
BG_DARK = "#0A0F1E"
TEXT_LIGHT = "#F8FAFC"
FONT_SIZE_MIN = 12

def _setup_style(ax, fig, title: str, accent_hex: str | None = None):
    """Apply navy/gold theme to figure and axes. accent_hex overrides gold for title/spines."""
    accent = accent_hex if accent_hex and isinstance(accent_hex, str) and len(accent_hex.strip()) >= 6 else None
    title_color = accent or GOLD
    spine_color = STEEL_BLUE
    fig.patch.set_facecolor(BG_DARK)
    ax.set_facecolor(BG_DARK)
    ax.tick_params(colors=TEXT_LIGHT)
    ax.xaxis.label.set_color(TEXT_LIGHT)
    ax.yaxis.label.set_color(TEXT_LIGHT)
    ax.title.set_color(title_color)
    ax.title.set_text(title)
    
    # Hide top and right spines for a cleaner, modern look
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color(spine_color)
    ax.spines['left'].set_color(spine_color)
    return fig, ax

def _hex_to_rgb_tuple(hex_str: str | None) -> tuple[float, float, float]:
    """Convert #RRGGBB to (r,g,b) in 0-1 for matplotlib."""
    if not hex_str or len(hex_str.strip()) < 6:
        return (0.1, 0.1, 0.12)
    h = hex_str.strip().lstrip("#")[:6]
    if len(h) < 6:
        return (0.1, 0.1, 0.12)
    try:
        r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
        return (r, g, b)
    except ValueError:
        return (0.1, 0.1, 0.12)

def _theme_colors(theme: Dict[str, Any] | None) -> Dict[str, tuple[float, float, float]]:
    t = theme or {}
    return {
        "bg": _hex_to_rgb_tuple(t.get("bg") or BG_DARK),
        "accent": _hex_to_rgb_tuple(t.get("accent") or STEEL_BLUE),
        "text": _hex_to_rgb_tuple(t.get("text_primary") or TEXT_LIGHT),
    }

# --- UNIVERSAL CHARTS ---

def chart_revenue(save_path: Path, periods: List[str] | None = None, values: List[float] | None = None, unit: str = "M", accent_hex: str | None = None) -> Path:
    import matplotlib.pyplot as plt # type: ignore[reportMissingImports]

    periods = periods or ["2024", "2025", "2026", "2027"]
    values = values if values is not None else [10.0, 25.0, 50.0, 100.0]
    n = min(len(periods), len(values))
    periods, values = periods[:n], values[:n]

    fig, ax = plt.subplots(figsize=(10, 6))
    fig, ax = _setup_style(ax, fig, f"Revenue Growth (${unit})", accent_hex=accent_hex)
    bar_color = accent_hex if accent_hex and len(str(accent_hex).strip()) >= 6 else STEEL_BLUE
    label_color = GOLD
    
    bars = ax.bar(periods, values, color=bar_color, linewidth=1.2, alpha=0.9)
    ax.set_ylabel(f"Revenue (${unit})", fontsize=12)
    ax.set_ylim(0, max(values) * 1.25 if values else 1) # Extra headroom for labels

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + (max(values) or 1) * 0.02,
            f"${int(val)}{unit}" if val >= 1 else f"${val}{unit}",
            ha="center", va="bottom", color=label_color, fontsize=11, fontweight="bold",
        )

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, facecolor=BG_DARK, edgecolor="none", bbox_inches="tight")
    plt.close()
    return save_path

def chart_sales_funnel(save_path: Path, stages: List[str] | None = None, percentages: List[float] | None = None, accent_hex: str | None = None) -> Path:
    import matplotlib.pyplot as plt # type: ignore[reportMissingImports]

    stages = stages or ["Leads", "MQL", "SQL", "Deal", "Closed"]
    percentages = percentages if percentages is not None else [100.0, 50.0, 20.0, 10.0, 5.0]
    n = min(len(stages), len(percentages))
    stages, percentages = stages[:n], percentages[:n]

    fig, ax = plt.subplots(figsize=(10, 6))
    fig, ax = _setup_style(ax, fig, "Sales Funnel (% conversion)", accent_hex=accent_hex)
    
    colors = []
    for pct in percentages:
        # FIX: Corrected gradient logic math
        t = max(0, min(1, (pct - 5.0) / 95.0))
        r = 0.04 + (0.83 - 0.04) * (1 - t)
        g = 0.06 + (0.69 - 0.06) * (1 - t)
        b = 0.12 + (0.22 - 0.12) * (1 - t)
        colors.append((r, g, b))

    bars = ax.barh(stages, percentages, color=colors, linewidth=1.2, alpha=0.95)
    ax.invert_yaxis() # Put "Leads" at the top
    ax.set_xlabel("% of Leads", fontsize=12)
    ax.set_xlim(0, max(percentages) * 1.15 if percentages else 110)

    for bar, val in zip(bars, percentages):
        ax.text(
            bar.get_width() + 2,
            bar.get_y() + bar.get_height() / 2,
            f"{int(val)}%",
            ha="left", va="center", color=GOLD_LIGHT, fontsize=11, fontweight="bold",
        )

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, facecolor=BG_DARK, edgecolor="none", bbox_inches="tight")
    plt.close()
    return save_path

def chart_team_growth(save_path: Path, months: List[str] | None = None, headcount: List[float] | None = None, accent_hex: str | None = None) -> Path:
    import matplotlib.pyplot as plt # type: ignore[reportMissingImports]

    months = months or ["Jan 2025", "Feb 2025", "Mar 2025", "Apr 2025"]
    headcount = headcount if headcount is not None else [20.0, 35.0, 52.0, 70.0]
    n = min(len(months), len(headcount))
    months, headcount = months[:n], headcount[:n]

    fig, ax = plt.subplots(figsize=(10, 6))
    fig, ax = _setup_style(ax, fig, "Team Growth (Headcount)", accent_hex=accent_hex)
    bar_color = accent_hex if accent_hex and len(str(accent_hex).strip()) >= 6 else STEEL_BLUE
    ax.bar(months, headcount, color=bar_color, linewidth=1.2, alpha=0.9)
    ax.set_ylabel("Headcount", fontsize=12)
    ax.set_ylim(0, max(headcount) * 1.2 if headcount else 1)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, facecolor=BG_DARK, edgecolor="none", bbox_inches="tight")
    plt.close()
    return save_path


def chart_market_opportunity(save_path: Path, labels: List[str] | None = None, sizes: List[float] | None = None, accent_hex: str | None = None) -> Path:
    import matplotlib.pyplot as plt # type: ignore[reportMissingImports]

    labels = labels or ["Enterprise", "Mid-market", "SMB"]
    sizes = sizes if sizes is not None else [45.0, 35.0, 20.0]
    n = min(len(labels), len(sizes))
    labels, sizes = labels[:n], sizes[:n]
    total = sum(sizes) or 1
    sizes_pct = [100 * v / total for v in sizes]

    fig, ax = plt.subplots(figsize=(8, 6))
    fig, ax = _setup_style(ax, fig, "Market Opportunity (%)", accent_hex=accent_hex)
    base = np.array([0.27, 0.51, 0.71])  # steel blue rgb
    colors = [tuple(np.clip(base * (1.0 - i * 0.15), 0, 1)) for i in range(n)]
    wedges, _, _ = ax.pie(sizes_pct, labels=labels, autopct="%1.0f%%", startangle=90, colors=colors, textprops={"color": TEXT_LIGHT})
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, facecolor=BG_DARK, edgecolor="none", bbox_inches="tight")
    plt.close()
    return save_path


# --- DYNAMIC THEME CHARTS (Fixed for AI generation) ---

def chart_bar_theme(save_path: Path, labels: List[str], values: List[float], title: str = "Comparison", theme: Dict[str, Any] | None = None) -> Path:
    import matplotlib.pyplot as plt # type: ignore[reportMissingImports]

    c = _theme_colors(theme)
    n = min(len(labels), len(values))
    labels, values = labels[:n], values[:n]
    if n < 2: return save_path

    fig, ax = plt.subplots(figsize=(5, 3.5))
    fig.patch.set_facecolor(c["bg"])
    ax.set_facecolor(c["bg"])
    
    bars = ax.bar(range(n), values, color=c["accent"], edgecolor=c["bg"], linewidth=1.5)
    ax.set_xticks(range(n))
    
    # FIX: Increased rotation to 45 degrees so long AI labels don't overlap
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=FONT_SIZE_MIN, color=c["text"])
    
    ax.set_title(title[:50], fontsize=max(12, FONT_SIZE_MIN), color=c["text"], pad=15)
    ax.tick_params(colors=c["text"])
    
    # Add data labels on top of bars
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval, f'{int(yval)}', ha='center', va='bottom', color=c["text"], fontsize=10)

    # Hide top/right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color(c["accent"])
    ax.spines['left'].set_color(c["accent"])

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, facecolor=c["bg"], edgecolor="none", bbox_inches="tight")
    plt.close()
    return save_path

def chart_pie_theme(save_path: Path, labels: List[str], values: List[float], title: str = "Share", theme: Dict[str, Any] | None = None) -> Path:
    """FIXED Pie Chart: Uses a legend instead of direct labels to prevent overlapping."""
    import matplotlib.pyplot as plt # type: ignore[reportMissingImports]

    c = _theme_colors(theme)
    n = min(len(labels), len(values))
    labels, values = labels[:n], values[:n]
    if n < 2: return save_path
    
    total = sum(values) or 1
    sizes = [100 * v / total for v in values]

    fig, ax = plt.subplots(figsize=(6, 4)) # Made slightly wider for the legend
    fig.patch.set_facecolor(c["bg"])
    ax.set_facecolor(c["bg"])
    
    # Create distinct colors based on the accent
    base_color = np.array(c["accent"])
    colors = [tuple(np.clip(base_color * (1.0 - (i * 0.2)), 0, 1)) for i in range(n)]

    # FIX: Remove labels from the pie itself, format percentages cleanly
    wedges, texts, autotexts = ax.pie(
        sizes, autopct="%1.0f%%", startangle=90, pctdistance=0.75,
        textprops={"fontsize": 10, "color": c["bg"], "fontweight": "bold"},
        colors=colors[:n], wedgeprops={"edgecolor": c["bg"], "linewidth": 1.5},
    )
    
    # FIX: Add a legend off to the right side
    ax.legend(wedges, labels, title="Categories", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1), 
              facecolor=c["bg"], edgecolor=c["bg"], labelcolor=c["text"])

    ax.set_title(title[:50], fontsize=max(12, FONT_SIZE_MIN), color=c["text"])
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, facecolor=c["bg"], edgecolor="none", bbox_inches="tight")
    plt.close()
    return save_path

def chart_line_theme(save_path: Path, labels: List[str], values: List[float], title: str = "Trend", theme: Dict[str, Any] | None = None) -> Path:
    import matplotlib.pyplot as plt # type: ignore[reportMissingImports]

    c = _theme_colors(theme)
    n = min(len(labels), len(values))
    labels, values = labels[:n], values[:n]
    if n < 2:
        return save_path
    fig, ax = plt.subplots(figsize=(5, 3.5))
    fig.patch.set_facecolor(c["bg"])
    ax.set_facecolor(c["bg"])
    ax.plot(range(n), values, color=c["accent"], linewidth=2, marker="o", markersize=6)
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=FONT_SIZE_MIN, color=c["text"])
    ax.set_title(title[:50], fontsize=max(12, FONT_SIZE_MIN), color=c["text"], pad=15)
    ax.tick_params(colors=c["text"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color(c["accent"])
    ax.spines["left"].set_color(c["accent"])
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, facecolor=c["bg"], edgecolor="none", bbox_inches="tight")
    plt.close()
    return save_path


def chart_gauge_theme(save_path: Path, value: float, title: str = "Score", theme: Dict[str, Any] | None = None, max_val: float = 100.0) -> Path:
    import matplotlib.pyplot as plt # type: ignore[reportMissingImports]

    c = _theme_colors(theme)
    fig, ax = plt.subplots(figsize=(4, 3), subplot_kw=dict(projection="polar"))
    theta = np.linspace(0, np.pi, 100)
    r = np.ones(100)
    ax.fill_between(theta, 0, r, color=(0.15, 0.15, 0.18))
    pct = max(0, min(1, value / max_val))
    ax.fill_between(theta[: int(len(theta) * pct)], 0, 1, color=c["accent"])
    ax.set_ylim(0, 1)
    ax.set_title(f"{title[:30]}\n{int(value)}", color=c["text"], fontsize=FONT_SIZE_MIN)
    ax.set_facecolor(c["bg"])
    fig.patch.set_facecolor(c["bg"])
    ax.set_xticklabels([])
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, facecolor=c["bg"], edgecolor="none", bbox_inches="tight")
    plt.close()
    return save_path


def render_dynamic_chart(
    save_path: Path,
    chart_type: str,
    spec: Dict[str, Any],
    theme: Dict[str, str] | None = None,
) -> Path | None:
    """Render bar, line, pie, or gauge from spec (title, labels, values). theme: hex dict (bg, accent, text_primary)."""
    title = (spec.get("title") or "Chart")[:50]
    labels = spec.get("labels") or []
    values = spec.get("values") or []
    n = min(len(labels), len(values))
    if n == 0:
        return None
    labels, values = labels[:n], values[:n]
    try:
        if chart_type == "bar":
            return chart_bar_theme(save_path, labels, values, title=title, theme=theme)
        if chart_type == "line":
            return chart_line_theme(save_path, labels, values, title=title, theme=theme)
        if chart_type == "pie":
            return chart_pie_theme(save_path, labels, values, title=title, theme=theme)
        if chart_type == "gauge":
            val = values[0] if values else 0
            return chart_gauge_theme(save_path, val, title=title, theme=theme)
        return chart_bar_theme(save_path, labels, values, title=title, theme=theme)
    except Exception:
        return None


def generate_all_charts(
    output_dir: Path,
    company_data: Dict[str, Any] | None = None,
    accent_color: str | None = None,
) -> List[Path]:
    """Generate the 4 universal business charts; return list of saved paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data = company_data or {}
    paths: List[Path] = []

    rev = data.get("revenue") or {}
    paths.append(chart_revenue(
        output_dir / "revenue.png",
        periods=rev.get("periods"),
        values=rev.get("values"),
        unit=rev.get("unit", "M"),
        accent_hex=accent_color,
    ))
    fun = data.get("funnel") or {}
    paths.append(chart_sales_funnel(
        output_dir / "funnel.png",
        stages=fun.get("stages"),
        percentages=fun.get("percentages"),
        accent_hex=accent_color,
    ))
    team = data.get("team_growth") or {}
    paths.append(chart_team_growth(
        output_dir / "team.png",
        months=team.get("months"),
        headcount=team.get("headcount"),
        accent_hex=accent_color,
    ))
    market = data.get("market") or {}
    paths.append(chart_market_opportunity(
        output_dir / "market.png",
        labels=market.get("labels"),
        sizes=market.get("sizes"),
        accent_hex=accent_color,
    ))
    return paths