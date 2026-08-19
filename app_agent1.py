"""Agent 1 · 每日热点 → 候选内容池 — standalone Streamlit app.

Run:
    streamlit run app_agent1.py

Scope: 真实采集 → 去重 → 评分 → 账号相关性判断 → 自动双语摘要/角度
       → 候选入池（pipeline=hot_topics）→ 自己的待审核池 → 反馈权重
"""
import os
import sys

import streamlit as st

st.set_page_config(page_title="Agent 1 · 每日热点 → 候选池", layout="wide")

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
    render_rank_chip,
    render_score_bars,
    render_section,
    render_status_pill,
    render_viral_dial,
)


def _db():
    from core import db

    db.init_db()
    return db


def _display_source(ev: dict) -> str:
    """Semantic source label for the UI.

    Hacker News items are community-shared links (often personal blogs /
    dev posts), NOT news outlets — so they are labeled '社区分享/开发者讨论'
    instead of being presented as news or official media.
    """
    src = ev.get("source", "")
    cat = ev.get("source_category", "")
    if "hacker" in cat.lower() or "hacker" in src.lower():
        return "Hacker News（社区分享/开发者讨论，非官方媒体）"
    if cat == "google_news":
        return src or "Google News"
    if cat == "gdelt":
        return "GDELT（全球新闻聚合）"
    if cat == "coingecko":
        return "CoinGecko（市场数据）"
    return f"{src}（{cat}）"


def _recompute_with_current_profile(raw_events: list) -> list:
    """Re-run pipeline scoring + relevance with the CURRENT account profile.

    raw_events are standardized events (pre-relevance). Changing the account
    profile must re-rank and re-decide, not keep stale results.
    """
    from core.pipeline import run_pipeline
    from core.models import Event

    evs = [Event.from_dict(e) for e in raw_events]
    result = run_pipeline(evs)
    return result["events"]


def _collect_hot_events():
    from agents.collectors import orchestrator
    from core.pipeline import run_pipeline
    from core.models import Event

    summary = orchestrator.collect_summary()
    events = [Event.from_dict(d) for d in summary["events"]]
    result = run_pipeline(events)
    return result, {
        "total": summary["total_events"],
        "by_source": summary["by_source"],
        "warnings": summary["warnings"],
        "deduped": result["deduped_count"],
        "removed": result["removed_count"],
    }, summary["events"]


def _collect_more_events():
    """Collect MORE events (larger per-source limits) for '需要更多热点'."""
    from agents.collectors import gdelt, google_news, hacker_news, orchestrator
    from core.pipeline import run_pipeline
    from core.models import Event

    events = []
    warnings = []
    # deeper fetch: Google News per-query limit ×3, HN ×30, GDELT retry
    gn = google_news.collect_more() if hasattr(google_news, "collect_more") else google_news.collect()
    events.extend(gn.events)
    warnings.extend(gn.warnings)
    hn = hacker_news.collect(limit=30)
    events.extend(hn.events)
    warnings.extend(hn.warnings)
    g = gdelt.collect()
    events.extend(g.events)
    warnings.extend(g.warnings)

    result = run_pipeline(events)
    return result["events"], {
        "total": len(events),
        "warnings": [{"source": w.source, "reason": w.reason} for w in warnings],
        "deduped": result["deduped_count"],
        "removed": result["removed_count"],
    }, [e.to_dict() for e in events]


def _load_hot_snapshot():
    from agents.collectors import snapshot
    from core.pipeline import run_pipeline
    from core.models import Event

    events = []
    for src in snapshot.list_snapshots():
        events.extend(snapshot.load_snapshot(src.replace(".json", "")))
    result = run_pipeline(events)
    return result, {
        "total": len(events),
        "by_source": {},
        "warnings": [{"source": "snapshot", "reason": "cached_public"}],
        "deduped": result["deduped_count"],
        "removed": result["removed_count"],
    }, [e.to_dict() for e in events]


def _auto_enrich(events, limit=8):
    from agents.enrichment import enrich_event
    from core.models import Event

    enriched = {}
    for ev_dict in events[:limit]:
        ev_obj = Event.from_dict(ev_dict)
        try:
            enriched[ev_dict.get("dedup_key") or ev_dict.get("url")] = enrich_event(ev_obj)
        except Exception:  # noqa: BLE001
            continue
    return enriched


def page_discovery():
    from agents import viral_index

    render_section("步骤 1 · 采集与评分")
    st.caption(
        f"真实公开数据 → 去重 → 爆款指数评分（≥{viral_index.VIRAL_THRESHOLD:.0f} 分入池）→ 账号相关性判断"
    )
    render_disclaimer()

    from core.account import current_profile_name, load_profile

    profile = load_profile()
    with st.expander(f"🎯 我方账号画像（{profile.get('name','')} · 当前激活）", expanded=False):
        st.markdown(
            f"- **账号名**: {profile.get('name')}\n"
            f"- **定位**: {profile.get('positioning')}\n"
            f"- **目标用户**: {profile.get('target_users')}\n"
            f"- **口吻**: {profile.get('voice')}\n"
            f"- **语言**: {profile.get('language')}\n"
            f"- **核心主题**: {profile.get('core_topics')}"
        )
        if st.button("✏️ 编辑账号画像（去设置页）"):
            st.session_state["jump_to_profile"] = True

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("采集今日热点", type="primary"):
            with st.spinner("采集真实公开数据源…"):
                result, cs, raw = _collect_hot_events()
                st.session_state["hot_events"] = result["events"]
                st.session_state["raw_events"] = raw
                st.session_state["collect_summary"] = cs
                st.session_state["auto_enriched"] = _auto_enrich(result["events"])
                st.rerun()
    with col2:
        if st.button("需要更多热点"):
            with st.spinner("追加采集更多真实热点…"):
                more, cs, more_raw = _collect_more_events()
                # 追加到现有列表（按 url/dedup_key 去重）
                existing = st.session_state.get("hot_events", [])
                raw_existing = st.session_state.get("raw_events", [])
                seen = {e.get("url") for e in existing}
                new_events = [e for e in more if e.get("url") not in seen]
                merged = existing + new_events
                raw_merged = raw_existing + [e for e in more_raw if e.get("url") not in seen]
                st.session_state["hot_events"] = merged
                st.session_state["raw_events"] = raw_merged
                st.session_state["collect_summary"] = {
                    **st.session_state.get("collect_summary", {}),
                    "total": cs["total"],
                    "deduped": len(merged),
                }
                st.session_state["auto_enriched"] = _auto_enrich(merged)
                st.rerun()
    with col3:
        if st.button("加载真实公开数据快照"):
            with st.spinner("加载 cached_public 快照…"):
                result, cs, raw = _load_hot_snapshot()
                st.session_state["hot_events"] = result["events"]
                st.session_state["raw_events"] = raw
                st.session_state["collect_summary"] = cs
                st.session_state["auto_enriched"] = _auto_enrich(result["events"])
                st.rerun()
    with col4:
        if st.button("生成真实快照"):
            from agents.collectors import google_news, hacker_news, snapshot

            for name, coll in (("google_news", google_news.collect), ("hacker_news", hacker_news.collect)):
                r = coll()
                snapshot.save_snapshot(r.events, name)
            st.success("快照已生成（google_news, hacker_news）")

    cs = st.session_state.get("collect_summary")
    if cs:
        render_metrics([
            ("采集总数", cs["total"], "raw"),
            ("去重后", cs["deduped"], f"移除 {cs['removed']}"),
        ])
        for w in cs["warnings"]:
            st.warning(f"来源失败: {w['source']} — {w['reason']}")

    if st.session_state.get("profile_recomputed"):
        st.info("账号画像已变更，以下相关性/跟进判断已按新画像重新计算。")
        st.session_state["profile_recomputed"] = False

    # 手动重算入口（若用户改了画像但已有列表）
    if st.session_state.get("raw_events") and st.session_state.get("hot_events"):
        if st.button("🔄 按当前账号画像重新计算相关性/排序"):
            recomputed = _recompute_with_current_profile(st.session_state["raw_events"])
            st.session_state["hot_events"] = recomputed
            st.session_state["auto_enriched"] = _auto_enrich(recomputed)
            st.rerun()

    events = st.session_state.get("hot_events", [])
    if events:
        # ------------------------------------------------------------------
        # 爆款指数 Top 10 榜单（viral index board）— 主视图
        # ------------------------------------------------------------------
        from agents import viral_index

        render_section("🔥 爆款指数 Top 10 榜单")
        st.caption(
            f"时效性×{viral_index.WEIGHTS['timeliness']:.0%} · "
            f"实操性×{viral_index.WEIGHTS['actionability']:.0%} · "
            f"视觉性×{viral_index.WEIGHTS['visual']:.0%} · "
            f"新颖性×{viral_index.WEIGHTS['novelty']:.0%} · "
            f"权威/相关性×{viral_index.WEIGHTS['authority']:.0%} · "
            f"满分 100，≥{viral_index.VIRAL_THRESHOLD:.0f} 分进入候选池"
        )
        board = viral_index.top10_board(events)
        render_metrics([
            ("共评分", board["total_scored"], "条新闻"),
            ("达标", board["qualified_count"], f"≥{board['threshold']:.0f} 分"),
        ])
        for rank, item in enumerate(board["top10"], 1):
            ev = item["event"]
            vi = item["viral_index"]
            qualifies = item["qualifies"]
            badge = "✅ 达标 · 可入池" if qualifies else "⛔ 未达标"
            # label must be PLAIN TEXT — st.expander does not render HTML in label
            label = (
                f"{rank}. 爆款指数 {vi:.0f} 分 [{badge}] ｜ "
                f"{item['core_insight'][:48]}"
            )
            with st.expander(label, expanded=(qualifies and rank <= 3)):
                # rich HTML visual (rank chip + dial + pill) rendered INSIDE
                chip = render_rank_chip(rank, top3=qualifies and rank <= 3)
                pill = (
                    '<span class="fs-pill fs-pill-green">✅ 达标 · 可入池</span>'
                    if qualifies
                    else '<span class="fs-pill fs-pill-gray">⛔ 未达标</span>'
                )
                head_html = (
                    f'<div style="display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap;">'
                    f"{chip}{render_viral_dial(vi, qualifies)}{pill}"
                    f'<span style="color:#374151;font-size:0.92rem;">{item["core_insight"][:56]}</span>'
                    f"</div>"
                )
                st.markdown(head_html, unsafe_allow_html=True)
                st.markdown('<div class="fs-card">', unsafe_allow_html=True)
                render_score_bars(item["dims"], item["reasons"])
                # 中文一句话内容介绍：优先复用 enrich 缓存，否则现场生成
                cn_intro = ""
                try:
                    from agents import zh_support
                    cn_intro = zh_support.summarize_zh(
                        ev.get("title", ""), ev.get("source", ""), ev.get("category", "")
                    )
                except Exception:  # noqa: BLE001
                    cn_intro = ""
                ev_url = ev.get("url", "")
                url_line = f" · 🔗 [打开原文]({ev_url})" if ev_url else " · 无原文链接"
                cn_clean = cn_intro.replace("事件摘要：", "").strip() if cn_intro else ""
                st.markdown(
                    f"**英文标题**: {ev['title'][:90]}\n\n"
                    f"**中文介绍**: {cn_clean[:160] or '（暂无中文摘要）'}\n\n"
                    f"**来源**: {_display_source(ev)} · **跟进决策**: `{ev.get('follow_decision','')}`{url_line}"
                )
                st.markdown(render_status_pill(ev.get("data_authenticity", "")), unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
                if qualifies:
                    if st.button("生成候选并加入待审核池", key=f"viral_pool_{rank}", type="primary"):
                        from agents.hot_topic_agent import build_candidates_for_event, persist_to_pool
                        from core.models import Event

                        ev_obj = Event.from_dict(ev)
                        cands = build_candidates_for_event(ev_obj)
                        ids = persist_to_pool(ev_obj, cands)
                        st.success(f"已生成 {len(cands)} 条候选并加入待审核池（id={ids}）")
                        st.rerun()
                else:
                    st.caption(
                        f"爆款指数未达 {viral_index.VIRAL_THRESHOLD:.0f} 分，不进入候选池。"
                    )

        # ------------------------------------------------------------------
        # 完整热点列表 — 折叠容器（默认收起，需要时展开）
        # ------------------------------------------------------------------
        with st.expander(f"📋 查看全部热点列表（{len(events)} 条）", expanded=False):
            sort_by = st.selectbox("排序方式", ["爆款指数（默认）", "优先级分数", "相关性分数", "跟进决策"])
            if sort_by == "爆款指数（默认）":
                events = sorted(
                    events,
                    key=lambda e: (e.get("priority_reasons", {}).get("viral_index", {}) or {}).get("viral_index", 0),
                    reverse=True,
                )
            elif sort_by == "相关性分数":
                events = sorted(
                    events,
                    key=lambda e: (e.get("priority_reasons", {}).get("relevance", {}) or {}).get("score", 0),
                    reverse=True,
                )
            elif sort_by == "跟进决策":
                order = {"follow": 0, "consider": 1, "caution": 2, "skip": 3}
                events = sorted(events, key=lambda e: order.get(e.get("follow_decision", ""), 4))
            else:
                events = sorted(events, key=lambda e: e.get("priority_score", 0), reverse=True)

            enriched = st.session_state.get("auto_enriched", {})
            for i, ev in enumerate(events, 1):
                pr = ev.get("priority_reasons", {})
                fr = pr.get("follow_reasons", [])
                rel = pr.get("relevance", {})
                decision = ev.get("follow_decision", "")
                key = ev.get("dedup_key") or ev.get("url")
                en = enriched.get(key, {})
                title_zh = en.get("title_zh", "")
                # 标题行：英文标题 + 中文翻译
                header = f"{i}. [{ev['priority_score']}] 【{decision}】{ev['title'][:75]}"
                if title_zh:
                    header += f"\n    📌 {title_zh[:60]}"
                with st.expander(header, expanded=False):
                    c1, c2, c3 = st.columns([1, 1, 1])
                    with c1:
                        st.markdown(f"**跟进决策**: `{decision}`")
                        render_authenticity_badge(ev.get("data_authenticity", ""))
                        st.markdown(f"**来源**: {_display_source(ev)}")
                        st.markdown(f"**类目**: {ev.get('category')}")
                    with c2:
                        st.markdown(f"**URL**: {ev.get('url')}")
                        st.markdown(f"**采集时间**: {ev.get('collected_at','')[:19]}")
                    with c3:
                        st.markdown(
                            f"**因子**: heat={pr.get('heat')} recency={pr.get('recency')} category={pr.get('category')}"
                        )
                        if rel:
                            st.markdown(
                                f"**相关性**: {rel.get('score')} · 主题 {rel.get('topics')} · 地区 {rel.get('regions')}"
                            )
                        if fr:
                            st.caption("；".join(fr))

                    if en:
                        st.markdown("**中文事件摘要**")
                        st.write(en.get("summary_zh_text", ""))
                        st.markdown("**中文主题与关键词**")
                        st.markdown(f"- **主题**: {en.get('topic_zh','')}")
                        st.markdown(f"- **关键词**: {en.get('keywords_zh','')}")
                        st.markdown("**中文内容角度（精确到本条）**")
                        for a in en.get("angles_zh", []):
                            st.markdown(f"- {a}")
                        st.markdown("**英文摘要**")
                        st.write(en.get("summary", ""))
                        st.markdown("**英文内容角度**")
                        for a in en.get("angles", []):
                            st.markdown(f"- {a}")
                    else:
                        st.caption("（摘要未生成）")

                    if st.button(
                        "生成候选并加入待审核池",
                        key=f"pool_{i}",
                        disabled=decision not in ("follow", "consider"),
                    ):
                        from agents.hot_topic_agent import build_candidates_for_event, persist_to_pool
                        from core.models import Event

                        # 爆款指数门槛：只有总分 ≥阈值 的选题才有资格进入候选池
                        vi = pr.get("viral_index", {})
                        if isinstance(vi, dict) and not vi.get("qualifies", False):
                            st.warning(
                                f"爆款指数未达 {viral_index.VIRAL_THRESHOLD:.0f} 分，该选题不进入候选池。"
                            )
                        else:
                            ev_obj = Event.from_dict(ev)
                            cands = build_candidates_for_event(ev_obj)
                            ids = persist_to_pool(ev_obj, cands)
                            st.session_state["pooled_ids"] = ids
                            st.success(f"已生成 {len(cands)} 条候选并加入待审核池（id={ids}）")
                            st.rerun()


def page_pool():
    render_section("待审核内容池（hot_topics）")
    st.caption("五状态人工审核：Draft / Needs Revision / Pending Review / Approved / Rejected")
    render_disclaimer()
    from agents import review

    status_filter = st.selectbox("状态筛选", ["全部"] + list(review.VALID_STATUSES))
    cands = review.list_candidates(
        status=None if status_filter == "全部" else status_filter,
        pipeline="hot_topics",
    )
    if not cands:
        st.info("暂无热点候选。请先在「热点发现」生成候选。")
    for c in cands:
        content = c.get("content", {})
        title_zh = content.get("title_zh", "")
        header = f"#{c['id']} [{c['status']}] {content.get('topic','')[:60]}"
        if title_zh:
            header += f" ｜ {title_zh[:40]}"
        with st.expander(header, expanded=False):
            st.markdown(f"**风险等级**: `{c['risk_level']}`")
            render_authenticity_badge(c.get("data_authenticity", ""))
            st.markdown("**中文事件摘要**")
            st.write(content.get("summary_zh", content.get("summary_zh_text", "")))
            st.markdown("**中文内容概括**")
            st.write(content.get("content_zh", ""))
            st.markdown("**关键词**: " + content.get("keywords_zh", ""))

            # --- 可直接粘贴到 X 发布的文案（可编辑 + 保存 + 一键复制）---
            st.markdown("**✏️ 发布文案（可编辑，可直接粘贴到 X）**")
            current_body = content.get("body_en", "")
            publish_text = st.text_area(
                "发布文案",
                value=current_body,
                height=160,
                key=f"pub_{c['id']}",
                label_visibility="collapsed",
            )
            st.code(publish_text or current_body, language="text", wrap_lines=True)
            if st.button("💾 保存修改", key=f"savepub_{c['id']}", disabled=not publish_text.strip() or publish_text == current_body):
                review.update_candidate_content(c["id"], publish_text, "编辑发布文案")
                st.success("发布文案已保存。")
                st.rerun()

            status = c["status"]
            st.markdown(f"**当前状态**: `{status}`")

            # --- 五状态流转：按当前状态显示可用动作 ---
            if status in ("Draft", "Needs Revision"):
                # 草稿/需修改 → 提交（或重新提交）审核
                btn_label = "重新提交审核" if status == "Needs Revision" else "提交审核"
                if status == "Needs Revision":
                    # 展示已保存的修改意见（来自最近一次 Needs Revision）
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
                # Approved / Rejected 终态
                st.caption(f"终态（{status}），不可再变更。")
                if status == "Rejected" and c.get("reject_reason"):
                    st.markdown(f"驳回原因：{c['reject_reason']}")
                # 终态也展示历史修改意见（便于复盘为何需修改）
                rv_logs = [r for r in review.review_log() if r["candidate_id"] == c["id"] and r["action"] == "request_revision"]
                if rv_logs:
                    st.markdown("**历史修改意见**：" + "；".join(r.get('note','') for r in rv_logs))

            # 审核历史（当前候选，含修改意见明文）
            logs = [r for r in review.review_log() if r["candidate_id"] == c["id"]]
            if logs:
                parts = []
                for r in logs:
                    t = f"{r['action']}({r['reviewed_at'][11:19]})"
                    if r["action"] == "request_revision" and r.get("note"):
                        t += f"「{r['note'][:30]}」"
                    parts.append(t)
                st.caption("审核历史：" + " → ".join(parts))

    st.divider()
    st.subheader("反馈学习（在线模型）")
    from agents import feedback_model

    status = feedback_model.model_status()
    st.markdown(
        f"- **模式**: `{status['mode']}`\n"
        f"- **训练样本**: {status['sample_count']} / {status['min_samples']}（达到后模型接管排序）\n"
        f"- 说明: {status['note']}"
    )
    weights = feedback_model.feature_weights()
    if weights:
        st.markdown("**模型特征权重**（正值 → 提高采用概率）")
        for w in sorted(weights, key=lambda x: -abs(x["weight"])):
            st.markdown(f"- `{w['feature']}`: {w['weight']:+.4f}")
    else:
        st.caption("样本不足或仅有单一标签，暂不展示模型权重（仍用规则权重排序）。")
    st.markdown("**规则权重（冷启动期生效）**")
    for w in review.feedback_snapshot():
        st.markdown(f"- `{w['dimension']}`: {w['weight']}")

    st.subheader("驳回原因统计")
    stats = review.reject_reason_stats()
    if not stats:
        st.caption("暂无驳回记录")
    for s in stats:
        st.markdown(f"- {s['reason']}: {s['count']} 次")


def page_settings():
    render_section("数据与设置")

    # ---- 账号画像管理（多画像，可保存/切换/删除）----
    st.subheader("对标账号画像（多画像管理）")
    from core.account import (
        REGION_PRESETS, current_profile_name, delete_profile, list_profiles,
        load_profile, save_profile, set_current_profile,
    )

    # 画像切换区
    profiles = list_profiles()
    cur = current_profile_name()
    c_sel, c_switch = st.columns([3, 1])
    with c_sel:
        sel = st.selectbox("已保存画像", ["(默认 FinSignal)"] + profiles, index=0 if cur == "FinSignal" else profiles.index(cur) + 1)
    with c_switch:
        if st.button("切换到此画像"):
            target = "FinSignal" if sel.startswith("(默认") else sel
            set_current_profile(target)
            raw = st.session_state.get("raw_events", [])
            if raw:
                st.session_state["hot_events"] = _recompute_with_current_profile(raw)
                st.session_state["auto_enriched"] = _auto_enrich(st.session_state["hot_events"])
                st.session_state["profile_recomputed"] = True
            st.success(f"已切换到画像：{target}")
            st.rerun()

    profile = load_profile()
    cur_region = profile.get("regions", ["Singapore"])[0] if profile.get("regions") else "Singapore"
    cur_rk = profile.get("region_keywords") or {}

    with st.form("profile_form"):
        name = st.text_input("画像名称", value=profile.get("name", ""), help="保存为独立画像，可随时切换")
        positioning = st.text_input("定位", value=profile.get("positioning", ""))
        target_users = st.text_input("目标用户", value=profile.get("target_users", ""))
        voice = st.text_input("口吻", value=profile.get("voice", ""))
        language = st.text_input("语言", value=profile.get("language", ""))
        core_topics = st.text_input(
            "核心主题（逗号分隔）",
            value=",".join(profile.get("core_topics", [])),
        )
        region_sel = st.selectbox(
            "目标地区（自动生成关键词）",
            list(REGION_PRESETS.keys()),
            index=list(REGION_PRESETS.keys()).index(cur_region) if cur_region in REGION_PRESETS else 0,
        )
        # 自动生成地区关键词预览（可手动补充）
        auto_kws = list(REGION_PRESETS[region_sel])
        st.caption(f"地区关键词（自动生成）：{', '.join(auto_kws)}")
        extra_kws = st.text_input(
            "额外地区关键词（逗号分隔，可选）",
            value="",
            help="在自动生成基础上追加关键词",
        )
        c1, c2 = st.columns(2)
        with c1:
            saved = st.form_submit_button("💾 保存画像")
        with c2:
            reset = st.form_submit_button("↩️ 恢复默认")
    if saved:
        merged_kws = {region_sel: tuple(REGION_PRESETS[region_sel])}
        for extra in [x.strip() for x in extra_kws.split(",") if x.strip()]:
            if extra not in merged_kws[region_sel]:
                merged_kws[region_sel] = merged_kws[region_sel] + (extra,)
        pname = save_profile({
            "name": name or region_sel,
            "positioning": positioning,
            "target_users": target_users,
            "voice": voice,
            "language": language,
            "core_topics": [t.strip() for t in core_topics.split(",") if t.strip()],
            "regions": [region_sel],
            "region_keywords": merged_kws,
        })
        raw = st.session_state.get("raw_events", [])
        if raw:
            st.session_state["hot_events"] = _recompute_with_current_profile(raw)
            st.session_state["auto_enriched"] = _auto_enrich(st.session_state["hot_events"])
            st.session_state["profile_recomputed"] = True
        st.success(f"画像「{pname}」已保存并切换，热点已按新画像重新计算。")
        st.rerun()
    if reset:
        reset_profile()
        raw = st.session_state.get("raw_events", [])
        if raw:
            st.session_state["hot_events"] = _recompute_with_current_profile(raw)
            st.session_state["auto_enriched"] = _auto_enrich(st.session_state["hot_events"])
            st.session_state["profile_recomputed"] = True
        st.success("已恢复默认画像（FinSignal），热点已重新计算。")
        st.rerun()

    # 删除画像区
    if profiles:
        st.markdown("**删除画像**")
        del_sel = st.selectbox("选择要删除的画像", profiles, key="del_prof")
        if st.button("🗑️ 删除所选画像"):
            delete_profile(del_sel)
            st.success(f"已删除画像：{del_sel}")
            st.rerun()

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
    st.subheader("数据来源")
    st.markdown(
        """
- Google News RSS（主要新闻发现）
- GDELT（新闻覆盖与地区交叉验证）
- Hacker News API（AI 技术/开发者讨论信号）
- CoinGecko（可选补充，Crypto/数字金融事件）
"""
    )


def main():
    _db()
    inject_theme()
    render_hero(
        "🔥 Agent 1 · 每日热点 → 候选内容池",
        "AI 金融内容候选系统 · 东南亚英文市场（新加坡为中心）· 真实公开数据驱动",
    )
    tabs = st.tabs(["热点发现", "待审核内容池", "数据与设置"])
    with tabs[0]:
        page_discovery()
    with tabs[1]:
        page_pool()
    with tabs[2]:
        page_settings()
    render_footer()


if __name__ == "__main__":
    main()
