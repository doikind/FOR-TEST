"""UI helpers: authenticity badge + disclaimer."""
import streamlit as st


def render_authenticity_badge(label: str) -> None:
    if label == "live_public":
        st.badge("live_public", color="green")
    elif label == "cached_public":
        st.badge("cached_public", color="orange")
    elif label == "simulated_demo":
        st.badge("simulated_demo · 模拟数据", color="red")
    else:
        st.caption(label)


def render_disclaimer() -> None:
    st.info(
        "This content is for informational purposes only and does not constitute investment advice."
    )
