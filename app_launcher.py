"""FinSignal Content Agent — launcher page.

两个 Agent 是**两个独立的 Streamlit 网页应用**，UI 完全分开：

  Agent 1 · 每日热点 → 候选内容池
      http://139.199.12.133:8501

  Agent 2 · 爆款拆解 → 二次创作
      http://139.199.12.133:8502

本地运行时可以共享一个 SQLite 数据库（finsignal.db）。分别部署到
两台服务器/端口后，两个应用位于独立运行环境，不共享本地 SQLite。
"""
import os
import sys

import streamlit as st

st.set_page_config(page_title="FinSignal Content Agent · Launcher", layout="wide")

AGENT1_URL = "http://139.199.12.133:8501"
AGENT2_URL = "http://139.199.12.133:8502"

BASE = os.path.dirname(os.path.abspath(__file__))
DEPS = os.path.join(BASE, ".py-deps")
if os.path.isdir(DEPS) and DEPS not in sys.path:
    sys.path.insert(0, DEPS)
if BASE not in sys.path:
    sys.path.insert(0, BASE)


def _is_up(url: str) -> bool:
    import urllib.request

    try:
        health_url = f"{url.rstrip('/')}/_stcore/health"
        with urllib.request.urlopen(health_url, timeout=5) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def main():
    st.title("FinSignal Content Agent · 启动器")
    st.caption("选择要打开的 Agent 网页（两个 Agent 为独立应用）")

    a1 = _is_up(AGENT1_URL)
    a2 = _is_up(AGENT2_URL)

    st.subheader("Agent 1 · 每日热点 → 候选内容池")
    st.markdown(
        "真实采集 → 去重 → 评分 → 账号相关性判断 → 自动双语摘要/角度 → 候选入池 → 人工审核"
    )
    st.markdown(
        f"[**打开 Agent 1**]({AGENT1_URL}) "
        f"· 状态: {'🟢 运行中' if a1 else '🔴 未启动'}"
    )
    if not a1:
        st.caption("公网应用尚未通过健康检查，请查看部署日志。")

    st.divider()

    st.subheader("Agent 2 · 爆款拆解 → 二次创作")
    st.markdown(
        "X 内容发现 → 同账号高表现 vs 普通筛选 → 六维度拆解 → 结构沉淀 → 围绕洞察生成 ≥3 条候选 → 资产库 + 表现记录"
    )
    st.markdown(
        f"[**打开 Agent 2**]({AGENT2_URL}) "
        f"· 状态: {'🟢 运行中' if a2 else '🔴 未启动'}"
    )
    if not a2:
        st.caption("公网应用尚未通过健康检查，请查看部署日志。")

    st.divider()
    st.info(
        "本地双端口运行时两个 Agent 可以共享 finsignal.db；分别部署到不同端口后，"
        "两个应用使用各自运行环境中的 SQLite，数据不会自动互通。"
    )


if __name__ == "__main__":
    main()
