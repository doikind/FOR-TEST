"""Agent 2 · 爆款拆解 → 二次创作 — standalone Streamlit app.

Run:
    streamlit run app_agent2.py

Scope: X 内容发现（或真实快照）→ 同账号高表现 vs 普通筛选 → 六维度拆解
       → 结构沉淀 → 围绕洞察生成 ≥3 条原创候选 → 写入资产库 + 表现记录
"""
import os
import sys

import streamlit as st

st.set_page_config(page_title="Agent 2 · 爆款拆解 → 二次创作", layout="wide")

BASE = os.path.dirname(os.path.abspath(__file__))
DEPS = os.path.join(BASE, ".py-deps")
if os.path.isdir(DEPS) and DEPS not in sys.path:
    sys.path.insert(0, DEPS)
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from ui.common import (  # noqa: E402
    inject_theme,
    render_authenticity_badge,
    render_disclaimer,
    render_footer,
    render_hero,
    render_metrics,
    render_section,
)


def _db():
    from core import db

    db.init_db()
    return db


def page_discovery():
    render_section("步骤 1 · X 内容发现与拆解")
    st.caption("X 公开内容发现（或合规真实快照）→ 同账号高表现 vs 普通 → 六维度拆解 → 结构沉淀")
    render_disclaimer()

    from agents import viral_agent

    DEFAULT_ACCOUNT = "AlphaSenseInc"
    PRESET_ACCOUNTS = [
        "AlphaSenseInc", "Finimize", "Hebbia", "OpenAI", "Anthropic",
        "MorganStanley", "BlackRock", "Nasdaq", "Bloomberg",
        # 新加坡市场案例账号
        "FintechSG", "MAS_sg",
    ]

    # 账号选择：预置常用账号 + 自定义
    preset = st.selectbox(
        "选择对标账号",
        PRESET_ACCOUNTS + ["✏️ 自定义账号…"],
        index=PRESET_ACCOUNTS.index(st.session_state.get("agent2_account", DEFAULT_ACCOUNT))
        if st.session_state.get("agent2_account", DEFAULT_ACCOUNT) in PRESET_ACCOUNTS
        else 0,
    )
    if preset == "✏️ 自定义账号…":
        custom = st.text_input("输入任意 screen_name", value=st.session_state.get("agent2_custom_account", ""))
        account = custom.strip()
    else:
        account = preset

    # 切换账号 → 自动重新发现拆解
    if account and account != st.session_state.get("agent2_account"):
        st.session_state["agent2_account"] = account
        if preset == "✏️ 自定义账号…":
            st.session_state["agent2_custom_account"] = account
        # 清掉旧账号的选题/候选缓存，避免串扰
        for k in ("agent2_insight", "agent2_insight_post", "agent2_candidates", "agent2_persist"):
            st.session_state.pop(k, None)
        with st.spinner(f"发现并拆解 @{account} …"):
            disc = viral_agent.run_discovery(account)
            st.session_state["agent2_discovery"] = disc
            if disc["posts"]:
                analysis = viral_agent._analyze(disc["posts"])
                st.session_state["agent2_analysis"] = analysis
                st.session_state["agent2_templates"] = viral_agent.build_insight_templates(analysis)
            else:
                st.session_state.pop("agent2_analysis", None)
                st.session_state.pop("agent2_templates", None)
            st.rerun()

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("重新发现 X 内容并拆解", type="primary"):
            with st.spinner("发现 X 公开内容（或加载真实快照）…"):
                disc = viral_agent.run_discovery(account or DEFAULT_ACCOUNT)
                st.session_state["agent2_discovery"] = disc
                if disc["posts"]:
                    analysis = viral_agent._analyze(disc["posts"])
                    st.session_state["agent2_analysis"] = analysis
                    st.session_state["agent2_templates"] = viral_agent.build_insight_templates(analysis)
                else:
                    st.session_state.pop("agent2_analysis", None)
                    st.session_state.pop("agent2_templates", None)
                st.rerun()
    with col2:
        if st.button("仅加载仓库快照（跳过实时）"):
            disc = viral_agent.run_discovery(account or DEFAULT_ACCOUNT, prefer_live=False)
            st.session_state["agent2_discovery"] = disc
            if disc["posts"]:
                analysis = viral_agent._analyze(disc["posts"])
                st.session_state["agent2_analysis"] = analysis
                st.session_state["agent2_templates"] = viral_agent.build_insight_templates(analysis)
            else:
                st.session_state.pop("agent2_analysis", None)
                st.session_state.pop("agent2_templates", None)
            st.rerun()
    with col3:
        if st.button("保存当前数据为真实快照"):
            disc = st.session_state.get("agent2_discovery")
            if not disc:
                st.warning("请先完成「发现 X 内容并拆解」。")
            elif disc.get("data_authenticity") == "live_public":
                path = viral_agent.save_live_snapshot(disc, account or DEFAULT_ACCOUNT)
                st.success(f"已保存真实快照: {path}")
            else:
                st.info("当前为快照数据，无需重复保存。")

    disc = st.session_state.get("agent2_discovery")
    if disc:
        for w in disc.get("warnings", []):
            st.warning(f"{w['source']}: {w['reason']}")
        st.info(f"模式: **{disc['mode']}** · 真实性: `{disc['data_authenticity']}` · {disc['note']}")
        render_authenticity_badge(disc.get("data_authenticity", ""))
        st.caption(f"共 {len(disc['posts'])} 条帖子（Post ID / 链接 / 片段 / 派生特征）")

        analysis = st.session_state.get("agent2_analysis")
        if analysis:
            render_metrics([
                ("高表现", analysis["high_count"], "同账号对比"),
                ("普通", analysis["normal_count"], "同账号对比"),
                ("分组阈值", analysis.get("group_threshold"), "相对表现分"),
            ])

            # 全部推文表格：组别 + 链接 + 时间 + 相对分 + 文本（含互动数据）
            group_map = {p["post_id"]: "高表现" for p in analysis["high_posts"]}
            group_map.update({p["post_id"]: "普通" for p in analysis["normal_posts"]})
            table_rows = []
            for p in disc["posts"]:
                m = p.get("metrics", {})
                table_rows.append(
                    {
                        "组别": group_map.get(p["post_id"], "—"),
                        "相对分": p.get("relative_score", 0),
                        "likes": m.get("likes", "—"),
                        "views": m.get("views", "—"),
                        "Post ID": p["post_id"],
                        "发布时间": p.get("posted_at", "")[:16],
                        "原文链接": p["source_url"],
                        "文本": p.get("snippet", "")[:90],
                    }
                )
            table_rows.sort(key=lambda r: (r["组别"] != "高表现", -r["相对分"]))
            st.dataframe(table_rows, use_container_width=True, hide_index=True)
            st.caption("链接可复制到浏览器打开原文；互动数据来自 X 公开页面，缺失为 —")

            # 选题（可直接带入步骤 2）
            st.subheader("选择选题 → 步骤 2")
            options = {
                f"[{group_map.get(p['post_id'],'?')}] {p['snippet'][:50]}...": p
                for p in disc["posts"]
            }
            sel_label = st.selectbox("选一条真实推文", list(options.keys()))
            if st.button("✏️ 用此推文作为选题", type="primary"):
                st.session_state["agent2_insight"] = options[sel_label]["snippet"]
                st.session_state["agent2_insight_post"] = options[sel_label]
                st.success("已选用作选题，请到「步骤 2」生成候选。")
                st.rerun()

            # 六维度拆解（简化展示）
            st.subheader("六维度拆解")
            dims = analysis["dimensions"]
            rows = []
            for dim, d in dims.items():
                rows.append(
                    {
                        "维度": {"topic": "选题", "hook": "Hook", "structure": "结构",
                                "information_density": "信息密度", "cta": "CTA",
                                "interaction": "互动设计"}.get(dim, dim),
                        "高表现": d["high"],
                        "普通": d["normal"],
                        "差值": d["diff"],
                        "证据": d["observed_level"],
                        "驱动(INFERRED)": d["inferred_driver"] or "—",
                    }
                )
            st.dataframe(rows, use_container_width=True, hide_index=True)

            with st.expander("证据分级说明"):
                for k, v in analysis["evidence_legend"].items():
                    st.markdown(f"- `{k}`: {v}")

            st.subheader("沉淀的结构模板")
            for t in st.session_state.get("agent2_templates", []):
                st.markdown(f"**{t['name']}** (`{t['evidence_level']}`)")
                for e in t["elements"]:
                    st.markdown(f"- {e}")


def page_creation():
    render_section("步骤 2 · 围绕洞察二次创作")
    st.caption("基于拆解洞察与结构模板 → 生成 ≥3 条原创英文候选 → 写入资产库")
    render_disclaimer()

    from agents import viral_agent

    # 自动带入步骤 1 选择的选题
    default_insight = st.session_state.get("agent2_insight", "")
    sel_post = st.session_state.get("agent2_insight_post")
    if sel_post:
        st.markdown(f"**选题来源**：`{sel_post['post_id']}` · 🔗 [打开原文]({sel_post['source_url']})")

    applied_tpl = st.session_state.get("agent2_apply_template")
    if applied_tpl:
        st.info(f"已应用结构模板 #{applied_tpl}（来自资产库），正文将按模板特征生成。")

    insight = st.text_input(
        "真实市场洞察（选题标题）",
        value=default_insight,
        placeholder="例如：Agentic AI is moving from demos to production in financial services",
    )
    if st.button("生成 ≥3 条原创候选并写入资产库", type="primary", disabled=not insight):
        disc = st.session_state.get("agent2_discovery")
        if not disc:
            st.warning("请先在「步骤 1：X 内容发现与拆解」完成发现与拆解。")
            st.stop()
        analysis = st.session_state.get("agent2_analysis") or viral_agent._analyze(disc["posts"])
        templates = st.session_state.get("agent2_templates") or viral_agent.build_insight_templates(analysis)
        bench = [p.get("snippet", "") for p in disc["posts"]]
        tpl_style = st.session_state.get("agent2_template_style")
        with st.spinner("生成候选…"):
            cands = viral_agent.create_candidates_from_insight(
                insight, analysis, templates, bench, disc.get("data_authenticity", "simulated_demo"),
                style=tpl_style,
            )
            result = viral_agent.persist_to_asset_library(
                insight, cands, analysis, templates, disc.get("data_authenticity", "simulated_demo")
            )
            st.session_state["agent2_candidates"] = cands
            st.session_state["agent2_persist"] = result
            st.rerun()

    persist = st.session_state.get("agent2_persist")
    if persist:
        st.success(f"已写入资产库：{persist['candidate_count']} 条候选 + {persist['template_count']} 个结构模板")

    cands = st.session_state.get("agent2_candidates", [])
    if cands:
        st.subheader(f"原创候选（{len(cands)}）")
        for i, c in enumerate(cands, 1):
            zh = c.get("angle_zh", "")
            label = f"{i}. {c['angle'][:50]}" + (f" ｜ {zh}" if zh else "")
            with st.expander(label, expanded=(i == 1)):
                if zh:
                    st.markdown(f"**选题角度（中文）**: {zh}")
                st.markdown(f"**Angle (EN)**: {c['angle']}")
                st.markdown("**Post (ready to publish)**")
                st.code(c["body_en"], language="text")
                st.markdown(
                    f"**Hook**: {c.get('hook','—')} · **CTA**: {c.get('cta','—')} · "
                    f"**Structure**: {c.get('structure','—')}"
                )
                st.markdown(
                    f"**Risk**: `{c['risk_level']}` · **Similarity**: {c['similarity'].get('score')} "
                    f"(flagged={c['similarity'].get('flagged')}) · **Mode**: {c.get('generation_mode','')}"
                )
                st.markdown(f"**Template hints**: {c.get('structure_hints')}")
                if c.get("risk_notes"):
                    st.warning("；".join(c["risk_notes"]))


def page_assets():
    render_section("内容资产库与表现记录")
    st.caption("Agent 2 生成内容 → 模拟发布 → 表现追踪（simulated_demo）")
    render_disclaimer()
    from agents import review

    assets = review.list_assets()
    deleted = review.list_deleted_assets()
    if not assets and not deleted:
        st.info("暂无资产。请在「步骤 2」生成候选后进入资产库。")
        return

    # candidate content by candidate_id → used for performance estimation
    _cand_by_id = {c["id"]: c.get("content", {}) for c in review.list_candidates()}

    # ---- 批量操作区：多选删除 / 多选标记已完成（仅未处理）----
    pending = [a for a in assets if a["status"] in ("draft", "approved")]
    if pending:
        st.subheader("批量操作")
        asset_options = {
            f"#{a['id']} [{a['status']}] {(a['title'] or '结构模板' or '')[:50]}": a["id"]
            for a in pending
        }
        selected = st.multiselect(
            "勾选要操作的资产（可多选）",
            list(asset_options.keys()),
            help="支持批量删除或批量标记为已完成（published）",
        )
        col_del, col_done = st.columns(2)
        with col_del:
            if st.button("🗑️ 删除所选资产", type="secondary", disabled=not selected):
                ids = [asset_options[k] for k in selected]
                n = review.delete_assets(ids)
                st.success(f"已删除 {n} 条资产")
                st.rerun()
        with col_done:
            if st.button("✅ 标记所选为已完成", type="primary", disabled=not selected):
                ids = [asset_options[k] for k in selected]
                n = review.mark_completed(ids)
                st.success(f"已将 {n} 条资产标记为已完成（published）")
                st.rerun()

    st.divider()

    # ---- 三个可折叠分组：未处理 / 已完成 / 已删除 ----
    groups = {
        "📋 未处理（draft / approved）": [a for a in assets if a["status"] in ("draft", "approved")],
        "✅ 已完成（published）": [a for a in assets if a["status"] == "published"],
        "🗑️ 已删除（归档）": deleted,
    }
    for gname, items in groups.items():
        with st.expander(f"{gname}（{len(items)}）", expanded=(gname.startswith("📋"))):
            if not items:
                st.caption("空")
                continue
            for a in items:
                title = a["title"] or (a.get("structure_template") and "结构模板") or f"#{a['id']}"
                st.markdown(f"**#{a['id']} [{a['status']}] {str(title)[:70]}**")
                render_authenticity_badge(a.get("data_authenticity", ""))
                if a.get("structure_template"):
                    st.markdown(f"结构模板：{a['structure_template'][:150]}")
                    # 模板应用闭环：应用此模板 → 带到步骤 2 生成
                    if st.button("✏️ 应用此模板生成候选", key=f"apply_tpl_{a['id']}"):
                        import json as _json

                        try:
                            tpl = _json.loads(a["structure_template"])
                        except Exception:  # noqa: BLE001
                            tpl = {"elements": []}
                        st.session_state["agent2_template_style"] = {
                            "hook_question": any("question" in e.lower() or "hook" in e.lower() for e in tpl.get("elements", [])),
                            "number_first": any("number" in e.lower() or "data" in e.lower() for e in tpl.get("elements", [])),
                            "cta_question": any("cta" in e.lower() or "question" in e.lower() for e in tpl.get("elements", [])),
                        }
                        st.session_state["agent2_apply_template"] = a["id"]
                        st.success(f"已应用结构模板 #{a['id']}，请到「步骤 2」输入选题生成候选。")
                        st.rerun()
                if a.get("performance"):
                    st.markdown(f"表现：{a['performance']}")
                if a.get("deleted_at"):
                    st.caption(f"删除时间：{a['deleted_at']}")
                # 未处理且为内容的资产 → 模拟发布录入（附规则化预估参考）
                if gname.startswith("📋") and not a.get("structure_template"):
                    content = _cand_by_id.get(a.get("candidate_id"), {})
                    est = review.estimate_performance(content) if content else None
                    with st.form(f"publish_{a['id']}"):
                        st.caption("模拟发布表现录入（simulated_demo）")
                        if est:
                            st.caption(
                                f"参考预估（规则化）：👍 {est['estimated_likes']} · 💬 {est['estimated_replies']} · "
                                f"🔁 {est['estimated_reposts']} （依据：{('、'.join(est['reasons'])) if est['reasons'] else '基础'}）"
                            )
                        likes = st.number_input("点赞", min_value=0, value=est["estimated_likes"] if est else 0, key=f"l_{a['id']}")
                        replies = st.number_input("回复", min_value=0, value=est["estimated_replies"] if est else 0, key=f"r_{a['id']}")
                        reposts = st.number_input("转帖", min_value=0, value=est["estimated_reposts"] if est else 0, key=f"x_{a['id']}")
                        if st.form_submit_button("模拟发布"):
                            review.simulate_publish(a["id"], {"likes": likes, "replies": replies, "reposts": reposts})
                            st.rerun()
                st.divider()


def page_pool():
    render_section("待审核内容池（content_creation）")
    st.caption("五状态人工审核：Draft / Needs Revision / Pending Review / Approved / Rejected")
    render_disclaimer()
    from agents import review

    status_filter = st.selectbox("状态筛选", ["全部"] + list(review.VALID_STATUSES))
    cands = review.list_candidates(
        status=None if status_filter == "全部" else status_filter,
        pipeline="content_creation",
    )
    if not cands:
        st.info("暂无候选。请先在「围绕洞察二次创作」生成候选。")
    for c in cands:
        content = c.get("content", {})
        header = f"#{c['id']} [{c['status']}] {content.get('topic','')[:60]}"
        with st.expander(header, expanded=False):
            st.markdown(f"**风险等级**: `{c['risk_level']}`")
            render_authenticity_badge(c.get("data_authenticity", ""))
            st.markdown("**英文正文**")
            st.text(content.get("body_en", "")[:500])

            status = c["status"]
            st.markdown(f"**当前状态**: `{status}`")
            if status in ("Draft", "Needs Revision"):
                btn_label = "重新提交审核" if status == "Needs Revision" else "提交审核"
                if status == "Needs Revision":
                    rv_logs = [r for r in review.review_log() if r["candidate_id"] == c["id"] and r["action"] == "request_revision"]
                    if rv_logs:
                        last = rv_logs[-1]
                        st.markdown(f"**📋 待处理修改意见**：{last.get('note','')}（{last['reviewed_at']}）")
                    if c.get("revision_note"):
                        st.markdown(f"**已保存修改意见**：{c['revision_note']}")
                if st.button(btn_label, key=f"sub_{c['id']}", type="primary"):
                    review.submit_for_review(c["id"])
                    st.rerun()
            elif status == "Pending Review":
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Approve", key=f"ap_{c['id']}", type="primary"):
                        review.approve(c["id"])
                        st.rerun()
                with col2:
                    reason = st.selectbox("驳回原因", list(review.REJECT_REASONS), key=f"rj_{c['id']}")
                    detail = st.text_input("补充说明（可选）", key=f"rjdt_{c['id']}")
                    if st.button("Reject", key=f"rjbtn_{c['id']}"):
                        review.reject(c["id"], reason, detail)
                        st.rerun()
                with col3:
                    note = st.text_input("修改意见", key=f"rv_{c['id']}")
                    if st.button("Needs Revision", key=f"rvbtn_{c['id']}", disabled=not note):
                        review.request_revision(c["id"], note)
                        st.rerun()
            else:
                st.caption(f"终态（{status}），不可再变更。")
                if status == "Rejected" and c.get("reject_reason"):
                    st.markdown(f"驳回原因：{c['reject_reason']}")
                rv_logs = [r for r in review.review_log() if r["candidate_id"] == c["id"] and r["action"] == "request_revision"]
                if rv_logs:
                    st.markdown("**历史修改意见**：" + "；".join(r.get('note','') for r in rv_logs))
            logs = [r for r in review.review_log() if r["candidate_id"] == c["id"]]
            if logs:
                parts = []
                for r in logs:
                    t = f"{r['action']}({r['reviewed_at'][11:19]})"
                    if r["action"] == "request_revision" and r.get("note"):
                        t += f"「{r['note'][:30]}」"
                    parts.append(t)
                st.caption("审核历史：" + " → ".join(parts))


def page_settings():
    render_section("数据与设置")
    st.subheader("数据真实性标签")
    st.markdown(
        """
- `live_public` — 实时公开数据
- `cached_public` — 真实公开数据快照（真实接口采集、离线保存）
- `simulated_demo` — 脱敏模拟数据（演示用，绝不冒充真实）
"""
    )
    st.subheader("免责声明")
    render_disclaimer()
    st.subheader("对标数据说明")
    st.markdown(
        """
- 主案例：Finimize（公开数据不足时按可得性切换 AlphaSense）
- AlphaSense / Hebbia 仅作扩展参考，不纳入主对比
- 当前无 X API，互动指标为脱敏模拟（simulated_demo），绝不冒充真实成绩
"""
    )

    st.divider()
    st.subheader("🇸🇬 案例：新加坡（Singapore）市场")
    with st.expander("案例使用说明", expanded=False):
        st.markdown(
            """
**场景**：面向新加坡（东南亚英文市场核心）的 AI 金融内容候选，
与 FinSignal 出海品牌定位一致（新加坡为中心）。

**预置账号**（步骤 1 下拉可直接选择）：
- `FintechSG` — 新加坡 fintech 生态账号（本地 startup / 融资 / 数字银行动态）
- `MASsg` — 新加坡金融管理局（MAS，政策与监管信号；数据可得性视公开通道而定）

**操作步骤**：
1. 步骤 1：选择 `FintechSG` → 「发现 X 内容并拆解」
2. 从表格中选一条真实推文作为选题（如本地 fintech startup 融资动态）
3. 步骤 2：生成 ≥3 条原创候选（英文正文 + 中文选题角度标注）
4. 资产库：模拟发布并录入表现（simulated_demo）

**推荐补充数据源**（Agent 1 侧）：Google News RSS 已含 "fintech Singapore" /
"digital finance" 主题查询，可交叉验证本地事件与 X 账号内容的覆盖面。
"""
        )
    with st.expander("注意事项", expanded=False):
        st.markdown(
            """
1. **数据可得性**：新加坡账号依赖 nitter/x.com 公开通道，可用性随公共镜像波动；失败时自动回退仓库快照（如有）或提示无数据。
2. **时区与时效**：新加坡为 UTC+8，与东南亚受众同区；排序中的时效因子按事件发布时间计算。
3. **监管敏感性**：MAS 与银行业话题（数字银行、支付牌照、反洗钱）务必引用原始来源；避免将监管动态表述为确定性利好/利空。
4. **本地视角**：内容应聚焦"新加坡/东南亚如何影响 AI 金融"，而非泛泛引用美国市场叙事；选题角度标注已支持此差异。
5. **合规**：所有输出附免责声明（非投资建议）；HIGH 风险内容禁止进入资产库；任何内容不自动发布。
6. **模拟数据**：互动指标/模拟发布表现一律标注 `simulated_demo`，绝不描述为真实运营成绩。
"""
        )


def main():
    _db()
    inject_theme()
    render_hero(
        "🚀 Agent 2 · 爆款内容拆解 → 二次创作",
        "AI 金融内容候选系统 · 东南亚英文市场（新加坡为中心）· 拆解驱动结构复用",
    )
    tabs = st.tabs(["X 内容发现与拆解", "围绕洞察二次创作", "待审核内容池", "内容资产库", "数据与设置"])
    with tabs[0]:
        page_discovery()
    with tabs[1]:
        page_creation()
    with tabs[2]:
        page_pool()
    with tabs[3]:
        page_assets()
    with tabs[4]:
        page_settings()
    render_footer()


if __name__ == "__main__":
    main()
