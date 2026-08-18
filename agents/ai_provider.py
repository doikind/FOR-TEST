"""AI provider abstraction — independent of business logic.

Modes (resolved in order):
  1. CacheProvider  — returns cached AI output for the same real input,
                      clearly labeled "AI 输出缓存" (never presented as live).
  2. TemplateProvider — deterministic rule/template output, labeled "模板模式".
  3. OpenAICompatProvider — optional OpenAI-compatible adapter (P1), labeled
                      "实时模型"; only used when a key is configured.

The business pipeline depends only on generate_candidates / summarize /
suggest_angles and never on which provider produced the text.
"""
import hashlib
import json
from typing import Any, Dict, List, Optional

from core import config, db
from core.models import Event


def _input_hash(event: Event, angles: List[str]) -> str:
    payload = json.dumps({"title": event.title, "angles": angles}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT output_json FROM ai_cache WHERE input_hash = ?", (key,)).fetchone()
        return json.loads(row["output_json"]) if row else None
    finally:
        conn.close()


def _cache_put(key: str, output: Dict[str, Any], mode: str) -> None:
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO ai_cache (input_hash, output_json, generation_mode) VALUES (?,?,?)",
            (key, json.dumps(output, ensure_ascii=False), mode),
        )
        conn.commit()
    finally:
        conn.close()


class TemplateProvider:
    """Deterministic, key-free content generation using rules/templates.

    Outputs bilingual (English content for X posting + Chinese for internal
    review). Every candidate carries EN body + ZH summary/angle/notes.
    """

    mode = "template"

    _ANGLES_ZH = {
        "ai": [
            "这项 AI 进展对金融服务业意味着什么",
            "产品/工程视角：底层发生了什么变化",
            "对金融科技开发者与投资者的下游影响",
        ],
        "fintech": [
            "此举对东南亚数字金融竞争格局意味着什么",
            "基础设施视角：通道、监管与在位者",
            "给投资者的信号：资本正在流向哪里",
        ],
        "investing": [
            "市场结构解读：投资者该关注什么",
            "挑战市场共识的数据点",
            "对组合与资产配置者的二阶效应",
        ],
        "crypto": [
            "面向主流金融的数字资产视角",
            "基础设施 vs 投机：如何区分信号与噪音",
            "监管与结算影响",
        ],
        "general": [
            "值得跟踪的、被低估的角度",
            "这对 AI 金融从业者意味着什么",
            "对更广泛金融科技生态的信号",
        ],
    }

    def suggest_angles(self, event: Event, n: int = 3) -> List[str]:
        cat = event.category or "general"
        angles = {
            "ai": [
                "Why this AI development matters for financial services",
                "The product/engineering angle: what changed under the hood",
                "Downstream impact for fintech builders and investors",
            ],
            "fintech": [
                "What this move means for Southeast Asia's digital finance race",
                "The infrastructure angle: rails, regulation, and incumbents",
                "Signal for investors: where capital is moving",
            ],
            "investing": [
                "The market-structure read: what investors should watch",
                "Data point that challenges the consensus narrative",
                "Second-order effects on portfolios and allocators",
            ],
            "crypto": [
                "The digital-asset angle for mainstream finance",
                "Infrastructure vs. speculation: separating signal from noise",
                "Regulatory and settlement implications",
            ],
            "general": [
                "The under-reported angle worth tracking",
                "What this means for AI-finance professionals",
                "A signal for the broader fintech ecosystem",
            ],
        }
        return angles.get(cat, angles["general"])[:n]

    def suggest_angles_zh(self, event: Event, n: int = 3) -> List[str]:
        cat = event.category or "general"
        return self._ANGLES_ZH.get(cat, self._ANGLES_ZH["general"])[:n]

    def summarize(self, event: Event) -> str:
        cat = event.category or "general"
        source = event.source or "public source"
        return (
            f"{event.title}. Reported via {source} "
            f"(category: {cat}). This is a template-generated summary for review; "
            f"verify against the original source before publishing."
        )

    def summarize_zh(self, event: Event) -> str:
        cat = event.category or "general"
        source = event.source or "public source"
        cat_zh = {"ai": "AI", "fintech": "金融科技", "investing": "投资研究",
                  "crypto": "数字金融", "general": "综合"}.get(cat, cat)
        return (
            f"事件：{event.title}。来源：{source}（类别：{cat_zh}）。"
            f"本条为模板生成的摘要，仅供审阅，发布前请核对原始来源。"
        )

    def generate_candidates(self, event: Event, angles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        angles = angles or self.suggest_angles(event)
        angles_zh = self.suggest_angles_zh(event, len(angles))
        candidates = []
        for i, angle in enumerate(angles[:3]):
            zh = angles_zh[i] if i < len(angles_zh) else angle
            body = (
                f"{event.title} — {angle}.\n\n"
                f"Source: {event.source} ({event.url}).\n"
                f"Fact check against the original before posting.\n"
                "This content is for informational purposes only and does not constitute investment advice."
            )
            candidates.append(
                {
                    "angle": angle,
                    "angle_zh": zh,
                    "target_interaction": "reply / discussion",
                    "body_en": body,
                    "body_zh": f"【中文说明】角度：{zh}。基于事件「{event.title}」，来源 {event.source}。发布前请核对原文。",
                    "hook": event.title[:120],
                    "hook_zh": f"钩子：{event.title[:60]}（直接抛出核心事实）",
                    "structure": "claim → context → source → CTA",
                    "cta": "What's your read on this?",
                    "cta_zh": "你怎么看？欢迎在评论区讨论。",
                    "fact_sources": [event.url],
                    "risk_notes": [],
                    "similarity": {},
                    "generation_mode": self.mode,
                }
            )
        return candidates


class CacheProvider:
    """Wraps a fallback provider with an AI-output cache (clearly labeled)."""

    mode = "cached"

    def __init__(self, fallback: Any):
        self.fallback = fallback

    def generate_candidates(self, event: Event, angles: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        if angles is None:
            try:
                angles = self.fallback.suggest_angles(event)
            except Exception:  # noqa: BLE001
                angles = TemplateProvider().suggest_angles(event)
        key = _input_hash(event, angles)
        cached = _cache_get(key)
        if cached:
            out = cached["output"]
            for c in out:
                c["generation_mode"] = "AI 输出缓存"
            return out
        try:
            out = self.fallback.generate_candidates(event, angles)
        except Exception:  # noqa: BLE001 — live model failure falls back to template
            out = TemplateProvider().generate_candidates(event, angles)
            for c in out:
                c["generation_mode"] = "模板模式（模型调用失败回退）"
            return out
        _cache_put(key, {"output": out}, self.mode)
        return out

    def suggest_angles(self, event: Event, n: int = 3) -> List[str]:
        try:
            return self.fallback.suggest_angles(event, n)
        except Exception:  # noqa: BLE001
            return TemplateProvider().suggest_angles(event, n)

    def suggest_angles_zh(self, event: Event, n: int = 3) -> List[str]:
        try:
            return self.fallback.suggest_angles_zh(event, n)
        except Exception:  # noqa: BLE001
            return TemplateProvider().suggest_angles_zh(event, n)

    def summarize(self, event: Event) -> str:
        try:
            return self.fallback.summarize(event)
        except Exception:  # noqa: BLE001
            return TemplateProvider().summarize(event)

    def summarize_zh(self, event: Event) -> str:
        try:
            return self.fallback.summarize_zh(event)
        except Exception:  # noqa: BLE001
            return TemplateProvider().summarize_zh(event)


class OpenAICompatProvider:
    """Optional OpenAI-compatible adapter (P1). Used only when a key is set."""

    mode = "live"

    def __init__(self):
        self._key = config.OPENAI_API_KEY
        self._base = config.OPENAI_BASE_URL
        self._model = config.OPENAI_MODEL

    def available(self) -> bool:
        return bool(self._key)

    def _chat(self, messages: List[Dict[str, str]]) -> str:
        import urllib.request

        payload = json.dumps({"model": self._model, "messages": messages}).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base.rstrip('/')}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._key}",
                "User-Agent": "finsignal/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
        return data["choices"][0]["message"]["content"]

    def summarize(self, event: Event) -> str:
        if not self.available():
            raise RuntimeError("no API key")
        return self._chat(
            [
                {"role": "system", "content": "You are a financial content editor. Summarize concisely."},
                {"role": "user", "content": f"Summarize this event for a fintech audience: {event.title}"},
            ]
        )

    def suggest_angles(self, event: Event, n: int = 3) -> List[str]:
        if not self.available():
            raise RuntimeError("no API key")
        text = self._chat(
            [
                {"role": "system", "content": "You are a fintech content strategist."},
                {"role": "user", "content": f"Suggest {n} distinct content angles for: {event.title}"},
            ]
        )
        return [line.strip("- ").strip() for line in text.splitlines() if line.strip()][:n]

    def suggest_angles_zh(self, event: Event, n: int = 3) -> List[str]:
        if not self.available():
            raise RuntimeError("no API key")
        text = self._chat(
            [
                {"role": "system", "content": "你是一名金融科技内容策略师，请用中文回答。"},
                {"role": "user", "content": f"为以下事件建议 {n} 个不同的内容角度：{event.title}"},
            ]
        )
        return [line.strip("- ").strip() for line in text.splitlines() if line.strip()][:n]

    def summarize_zh(self, event: Event) -> str:
        if not self.available():
            raise RuntimeError("no API key")
        return self._chat(
            [
                {"role": "system", "content": "你是一名金融内容编辑，请用中文简洁总结。"},
                {"role": "user", "content": f"用中文为金融科技受众总结该事件：{event.title}"},
            ]
        )


def get_provider() -> Any:
    """Resolve provider: cache -> live(if key) -> template."""
    template = TemplateProvider()
    live = OpenAICompatProvider()
    if live.available():
        # live generation, wrapped in cache for replayability
        return CacheProvider(live)
    return CacheProvider(template)
