"""Replace st.header with render_section in app_agent1.py."""
import io

p = r"F:\deep\finsignal-content-agent\app_agent1.py"
src = io.open(p, encoding="utf-8").read()
replacements = [
    ('st.header("Agent 1 · 待审核内容池（hot_topics）")', 'render_section("待审核内容池（hot_topics）")'),
    ('st.header("数据与设置（Agent 1）")', 'render_section("数据与设置")'),
]
for old, new in replacements:
    if old in src:
        src = src.replace(old, new)
        print("REPLACED:", old)
    else:
        print("NOT FOUND:", old)
io.open(p, "w", encoding="utf-8", newline="").write(src)
