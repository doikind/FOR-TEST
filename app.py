"""FinSignal Content Agent — launcher page.

两个 Agent 是**两个独立的 Streamlit 网页应用**（各自端口），UI 完全分开：

  Agent 1 · 每日热点 → 候选内容池    http://localhost:8501
      streamlit run app_agent1.py

  Agent 2 · 爆款拆解 → 二次创作       http://localhost:8502
      streamlit run app_agent2.py

共享一个 SQLite 数据库（finsignal.db），但各自页面只显示自己 pipeline 的数据：
  - Agent 1 候选：pipeline = hot_topics
  - Agent 2 候选：pipeline = content_creation
"""
import os
import subprocess
import sys

import streamlit as st

st.set_page_config(page_title="FinSignal Content Agent · Launcher", layout="wide")

BASE = os.path.dirname(os.path.abspath(__file__))
DEPS = os.path.join(BASE, ".py-deps")
if os.path.isdir(DEPS) and DEPS not in sys.path:
    sys.path.insert(0, DEPS)
if BASE not in sys.path:
    sys.path.insert(0, BASE)


def _is_up(port: int) -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=3) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def main():
    st.title("FinSignal Content Agent · 启动器")
    st.caption("选择要打开的 Agent 网页（两个 Agent 为独立应用）")

    a1 = _is_up(8501)
    a2 = _is_up(8502)

    st.subheader("Agent 1 · 每日热点 → 候选内容池")
    st.markdown(
        "真实采集 → 去重 → 评分 → 账号相关性判断 → 自动双语摘要/角度 → 候选入池 → 人工审核"
    )
    st.markdown(
        f"[**打开 Agent 1**](http://localhost:8501) "
        f"· 状态: {'🟢 运行中' if a1 else '🔴 未启动'}"
    )
    if not a1:
        st.code("streamlit run app_agent1.py --server.port 8501", language="bash")

    st.divider()

    st.subheader("Agent 2 · 爆款拆解 → 二次创作")
    st.markdown(
        "X 内容发现 → 同账号高表现 vs 普通筛选 → 六维度拆解 → 结构沉淀 → 围绕洞察生成 ≥3 条候选 → 资产库 + 表现记录"
    )
    st.markdown(
        f"[**打开 Agent 2**](http://localhost:8502) "
        f"· 状态: {'🟢 运行中' if a2 else '🔴 未启动'}"
    )
    if not a2:
        st.code("streamlit run app_agent2.py --server.port 8502", language="bash")

    st.divider()
    st.info(
        "两个 Agent 共享 finsignal.db，但各自页面只展示自己 pipeline 的候选："
        "Agent 1 = hot_topics，Agent 2 = content_creation。数据不互相串扰。"
    )


if __name__ == "__main__":
    main()
