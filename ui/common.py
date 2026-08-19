"""UI helpers: theme, authenticity badge, disclaimer, cards, score bars.

Design system (per ui-ux-pro-max audit):
  - 8px spacing scale, 16px body, 1.5 line-height
  - semantic colors: info #0F6CBD / success #2E7D32 / warning #B26A00 / danger #C62828
  - cards: 1px border, 12px radius, subtle shadow, generous padding
  - never rely on color alone: badges carry text + icon
"""
import streamlit as st

# ---------------------------------------------------------------------------
# Theme tokens
# ---------------------------------------------------------------------------
INFO = "#0F6CBD"
SUCCESS = "#2E7D32"
WARNING = "#B26A00"
DANGER = "#C62828"
MUTED = "#6B7280"

_STATUS_COLOR = {
    "live_public": SUCCESS,
    "cached_public": WARNING,
    "simulated_demo": DANGER,
}
_STATUS_LABEL = {
    "live_public": "live_public · 实时公开",
    "cached_public": "cached_public · 真实快照",
    "simulated_demo": "simulated_demo · 模拟数据",
}
_STATUS_ICON = {
    "live_public": "🟢",
    "cached_public": "🟠",
    "simulated_demo": "🔴",
}

_THEME_CSS = f"""
<style>
/* ---- base typography ---- */
html, body, [class*="st-"] {{
  font-size: 16px;
}}
.stApp {{
  background: #F7F9FC;
}}
.block-container {{
  padding-top: 2.2rem;
  padding-bottom: 4rem;
  max-width: 1280px;
}}

/* ---- hero header ---- */
.fs-hero {{
  padding: 1.25rem 1.5rem 1rem;
  border-radius: 14px;
  background: linear-gradient(135deg, #0F6CBD 0%, #14589B 100%);
  color: #fff;
  margin-bottom: 1.25rem;
  box-shadow: 0 4px 14px rgba(15, 108, 189, 0.18);
}}
.fs-hero h1 {{
  color: #fff !important;
  font-size: 1.65rem !important;
  margin: 0 0 0.25rem !important;
  letter-spacing: 0.2px;
}}
.fs-hero .fs-sub {{
  color: rgba(255,255,255,0.88) !important;
  font-size: 0.95rem;
  margin: 0;
}}

/* ---- generic card ---- */
.fs-card {{
  background: #fff;
  border: 1px solid #E5EAF0;
  border-radius: 12px;
  padding: 0.9rem 1.1rem;
  margin-bottom: 0.75rem;
  box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
}}

/* ---- score bar (viral index dimensions) ---- */
.fs-bar-row {{
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin: 0.35rem 0;
}}
.fs-bar-label {{
  width: 92px;
  flex: 0 0 92px;
  font-size: 0.82rem;
  color: #374151;
  text-align: right;
  white-space: nowrap;
}}
.fs-bar-track {{
  flex: 1;
  height: 9px;
  border-radius: 6px;
  background: #EEF2F6;
  overflow: hidden;
}}
.fs-bar-fill {{
  height: 100%;
  border-radius: 6px;
  transition: width 0.35s ease;
}}
.fs-bar-val {{
  width: 38px;
  flex: 0 0 38px;
  font-size: 0.82rem;
  font-weight: 600;
  color: #111827;
  text-align: right;
}}

/* ---- big viral score dial ---- */
.fs-dial {{
  display: inline-flex;
  align-items: baseline;
  gap: 0.35rem;
  font-weight: 700;
}}
.fs-dial .num {{ font-size: 2.1rem; line-height: 1; }}
.fs-dial .unit {{ font-size: 0.95rem; color: #6B7280; }}

/* ---- status pill (badge) ---- */
.fs-pill {{
  display: inline-block;
  padding: 0.16rem 0.6rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.2px;
  vertical-align: middle;
}}
.fs-pill-green {{ background:#E8F5E9; color:#1B5E20; border:1px solid #A5D6A7; }}
.fs-pill-orange{{ background:#FFF3E0; color:#B26A00; border:1px solid #FFCC80; }}
.fs-pill-red   {{ background:#FDECEA; color:#B71C1C; border:1px solid #F1B0A8; }}
.fs-pill-gray  {{ background:#EEF2F6; color:#4B5563; border:1px solid #D1D9E0; }}

/* ---- metric card row ---- */
.fs-metrics {{
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin: 0.75rem 0 1rem;
}}
.fs-metric {{
  flex: 1 1 150px;
  background: #fff;
  border: 1px solid #E5EAF0;
  border-radius: 12px;
  padding: 0.7rem 0.9rem;
  box-shadow: 0 1px 3px rgba(16, 24, 40, 0.05);
}}
.fs-metric .k {{ font-size: 0.78rem; color: #6B7280; margin-bottom: 0.2rem; }}
.fs-metric .v {{ font-size: 1.45rem; font-weight: 700; color: #111827; line-height: 1.1; }}
.fs-metric .d {{ font-size: 0.78rem; color: #9CA3AF; margin-top: 0.15rem; }}

/* ---- section heading ---- */
.fs-section {{
  font-size: 1.05rem;
  font-weight: 700;
  color: #111827;
  margin: 1.4rem 0 0.6rem;
  padding-left: 0.55rem;
  border-left: 4px solid {INFO};
  line-height: 1.3;
}}

/* ---- footer ---- */
.fs-footer {{
  margin-top: 2.5rem;
  padding-top: 1rem;
  border-top: 1px solid #E5EAF0;
  color: #9CA3AF;
  font-size: 0.8rem;
  text-align: center;
}}

/* ---- rank number chip ---- */
.fs-rank {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 26px;
  height: 26px;
  border-radius: 8px;
  background: {INFO};
  color: #fff;
  font-weight: 700;
  font-size: 0.85rem;
  margin-right: 0.45rem;
}}
.fs-rank.top {{ background: {DANGER}; }}

/* ---- caption tweaks ---- */
.stCaption, [data-testid="stCaptionContainer"] p {{
  color: #6B7280;
}}
</style>
"""


def inject_theme() -> None:
    """Inject the global design-system CSS (call once at app start)."""
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------
def render_hero(title: str, subtitle: str) -> None:
    """Gradient hero header shared by both agents."""
    st.markdown(
        f'<div class="fs-hero"><h1>{title}</h1>'
        f'<p class="fs-sub">{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def render_section(title: str) -> None:
    st.markdown(f'<div class="fs-section">{title}</div>', unsafe_allow_html=True)


def render_footer() -> None:
    st.markdown(
        '<div class="fs-footer">FinSignal Content Agent · 内容仅供信息参考，不构成投资建议</div>',
        unsafe_allow_html=True,
    )


def render_metrics(items: list) -> None:
    """items: list of (label, value, detail|None)."""
    cards = []
    for label, value, detail in items:
        d = f'<div class="d">{detail}</div>' if detail else ""
        cards.append(
            f'<div class="fs-metric"><div class="k">{label}</div>'
            f'<div class="v">{value}</div>{d}</div>'
        )
    st.markdown(f'<div class="fs-metrics">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_viral_dial(score: float, qualifies: bool) -> str:
    color = SUCCESS if qualifies else (WARNING if score >= 60 else MUTED)
    return (
        f'<span class="fs-dial"><span class="num" style="color:{color}">'
        f"{score:.0f}</span><span class=\"unit\">/100</span></span>"
    )


def render_status_pill(label: str) -> str:
    color = {
        "live_public": "green",
        "cached_public": "orange",
        "simulated_demo": "red",
    }.get(label, "gray")
    text = _STATUS_LABEL.get(label, label)
    return f'<span class="fs-pill fs-pill-{color}">{_STATUS_ICON.get(label,"")} {text}</span>'


def render_score_bars(dims: dict, reasons: dict | None = None) -> None:
    """Render five dimension score bars with optional inline reasons."""
    colors = {
        "timeliness": INFO,
        "actionability": "#7C3AED",
        "visual": "#0891B2",
        "novelty": "#D97706",
        "authority": "#059669",
    }
    labels = {
        "timeliness": "时效性",
        "actionability": "实操性",
        "visual": "视觉性",
        "novelty": "新颖性",
        "authority": "权威/相关性",
    }
    rows = []
    for k in ("timeliness", "actionability", "visual", "novelty", "authority"):
        val = dims.get(k, 0)
        pct = min(100, max(0, val))
        rows.append(
            f'<div class="fs-bar-row">'
            f'<span class="fs-bar-label">{labels[k]}</span>'
            f'<span class="fs-bar-track"><span class="fs-bar-fill" style="width:{pct:.0f}%;'
            f'background:{colors[k]}"></span></span>'
            f'<span class="fs-bar-val">{val:.0f}</span></div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)
    if reasons:
        parts = []
        for k in ("timeliness", "actionability", "visual", "novelty", "authority"):
            why = reasons.get(k) or []
            if why:
                parts.append(f"**{labels[k]}**：" + "；".join(why))
        if parts:
            with st.expander("评分理由", expanded=False):
                for p in parts:
                    st.markdown(p)


def render_rank_chip(rank: int, top3: bool = False) -> str:
    cls = "fs-rank top" if top3 else "fs-rank"
    return f'<span class="{cls}">{rank}</span>'


def render_authenticity_badge(label: str) -> None:
    if label in _STATUS_LABEL:
        st.markdown(render_status_pill(label), unsafe_allow_html=True)
    else:
        st.caption(label)


def render_disclaimer() -> None:
    st.markdown(
        '<div style="font-size:0.8rem;color:#6B7280;background:#FFF8E6;'
        'border:1px solid #F0E3B6;border-radius:8px;padding:0.4rem 0.7rem;'
        'margin-bottom:0.75rem;">'
        "⚠️ This content is for informational purposes only and does not constitute "
        "investment advice.</div>",
        unsafe_allow_html=True,
    )
