"""Replace st.header with render_section in app_agent2.py."""
import io

p = r"F:\deep\finsignal-content-agent\app_agent2.py"
src = io.open(p, encoding="utf-8").read()
replacements = [
    ('st.header("Agent 2 · 步骤 2：围绕洞察二次创作")', 'render_section("步骤 2 · 围绕洞察二次创作")'),
    ('st.header("Agent 2 · 内容资产库与表现记录")', 'render_section("内容资产库与表现记录")'),
    ('st.header("Agent 2 · 待审核内容池（content_creation）")', 'render_section("待审核内容池（content_creation）")'),
    ('st.header("数据与设置（Agent 2）")', 'render_section("数据与设置")'),
]
for old, new in replacements:
    if old in src:
        src = src.replace(old, new)
        print("REPLACED:", old)
    else:
        print("NOT FOUND:", old)
io.open(p, "w", encoding="utf-8", newline="").write(src)
