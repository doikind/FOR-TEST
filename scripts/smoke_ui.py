"""Smoke-test the new UI components render without exceptions."""
import sys

sys.path.insert(0, r"F:\deep\finsignal-content-agent")

# Verify all components are importable and callable shapes are right
from ui.common import (  # noqa: E402
    inject_theme,
    render_authenticity_badge,
    render_disclaimer,
    render_footer,
    render_hero,
    render_metrics,
    render_rank_chip,
    render_score_bars,
    render_section,
    render_status_pill,
    render_viral_dial,
)

assert "fs-hero" in __import__("ui.common", fromlist=["x"])._THEME_CSS
assert render_status_pill("live_public").startswith('<span class="fs-pill')
assert render_status_pill("simulated_demo")  # red pill
assert render_viral_dial(85, True)  # green dial
assert render_viral_dial(50, False)  # gray dial
assert render_rank_chip(1, top3=True).startswith('<span class="fs-rank top"')
assert render_rank_chip(9)  # normal chip
print("UI components OK")
