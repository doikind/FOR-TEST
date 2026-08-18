"""Chinese support for Agent 1 hot topics.

Two jobs:
  1. translate_title — rough EN→ZH translation of a headline (deterministic,
     key-free, good enough for quick browsing).
  2. topic_angles_zh — precise Chinese content angles anchored to THIS post's
     theme + keywords (not generic theory).

Because we have no LLM key, translation/angle generation is rule-based:
  - split the title into content words, translate known financial/AI terms,
    keep tickers/numbers/entities as-is.
  - extract theme + keywords from the title and weave them into the angle
    templates so the angles are specific to the post, not generic.
"""
import re
from typing import Dict, List, Tuple

# --- tiny finance/AI glossary (EN -> ZH) ------------------------------------
_GLOSSARY = {
    # AI
    "ai": "AI", "artificial intelligence": "人工智能", "machine learning": "机器学习",
    "llm": "大语言模型", "openai": "OpenAI", "anthropic": "Anthropic", "model": "模型",
    "models": "模型", "agent": "智能体", "agents": "智能体", "agentic": "智能体化",
    "deep learning": "深度学习", "neural": "神经网络", "algorithm": "算法",
    "training": "训练", "inference": "推理", "compute": "算力", "hallucination": "幻觉",
    "startup": "创业公司", "startups": "创业公司", "venture": "风险投资",
    "funding": "融资", "raised": "融资", "round": "轮次",
    # fintech
    "fintech": "金融科技", "payment": "支付", "payments": "支付", "bank": "银行",
    "banks": "银行", "digital bank": "数字银行", "neobank": "新型银行",
    "wallet": "钱包", "remittance": "汇款", "remit": "汇款", "lending": "贷款",
    "credit": "信贷", "insurance": "保险", "blockchain": "区块链", "stablecoin": "稳定币",
    "cbdc": "央行数字货币", "crypto": "加密资产", "bitcoin": "比特币", "ethereum": "以太坊",
    "token": "代币", "tokens": "代币", "exchange": "交易所", "brokerage": "券商",
    # investing / markets
    "stock": "股票", "stocks": "股票", "market": "市场", "markets": "市场",
    "invest": "投资", "investing": "投资", "investor": "投资者", "investors": "投资者",
    "fund": "基金", "funds": "基金", "etf": "ETF", "etfs": "ETF", "ipo": "IPO",
    "valuation": "估值", "trading": "交易", "equity": "股权", "bonds": "债券",
    "yield": "收益率", "margin": "利润率", "earnings": "财报", "revenue": "营收",
    "quarter": "季度", "forecast": "预测", "guidance": "业绩指引", "price": "价格",
    "asset": "资产", "assets": "资产", "portfolio": "投资组合", "capital": "资本",
    "capex": "资本开支", "infrastructure": "基础设施", "data center": "数据中心",
    "data centers": "数据中心", "semiconductor": "半导体", "chips": "芯片",
    "chip": "芯片", "analyst": "分析师", "analysts": "分析师", "ceo": "CEO",
    "regulation": "监管", "regulator": "监管机构", "regulatory": "监管",
    "policy": "政策", "central bank": "央行", "rate": "利率", "rates": "利率",
    "inflation": "通胀", "growth": "增长", "downgrade": "下调", "upgrade": "上调",
    # region
    "singapore": "新加坡", "southeast asia": "东南亚", "china": "中国", "us": "美国",
    "japan": "日本", "europe": "欧洲", "global": "全球", "asia": "亚洲",
    "wealth": "财富", "digital finance": "数字金融", "investment": "投资",
    "research": "研究", "security": "安全", "governance": "治理", "risk": "风险",
    # common verbs / entities in headlines
    "launches": "推出", "launched": "推出", "launch": "推出", "targets": "瞄准",
    "warns": "警告", "warn": "警告", "report": "报告", "reports": "报告",
    "watchdog": "监管机构", "financial watchdog": "金融监管机构",
    "raises": "融资", "raised": "融资", "raise": "融资",
    "acquires": "收购", "acquired": "收购",
    "agreement": "协议", "partnership": "合作", "deal": "交易", "merger": "并购",
    "acquisition": "收购", "leads": "领先", "surge": "激增", "surges": "激增",
    "plunge": "暴跌", "plunges": "暴跌", "soars": "飙升", "jump": "跳涨",
    "driven": "驱动", "decentralized": "去中心化", "forum": "论坛", "digital": "数字化",
    "cashback": "返现", "credit": "信贷", "rewards": "奖励", "card": "卡",
    "debut": "首发", "approves": "批准", "approved": "批准", "plans": "计划",
    "plan": "计划", "expects": "预期", "seen": "出现", "first": "首个",
}

# generic words to drop from the keyword list
_STOP = {"the", "a", "an", "and", "or", "of", "in", "on", "to", "for", "with",
         "is", "are", "was", "were", "be", "been", "its", "this", "that",
         "how", "why", "what", "who", "when", "will", "would", "can", "could",
         "should", "may", "might", "new", "as", "at", "by", "from", "into",
         "over", "under", "vs", "per", "more", "most", "after", "before"}

_ANGLE_ZH_TPL = [
    "{topic} 对新加坡/东南亚 AI 金融生态的影响",
    "{topic} 背后的数据与信号解读",
    "围绕 {topic} 的投资者视角与风险点",
]


def _tokenize(title: str) -> List[str]:
    words = re.findall(r"[A-Za-z0-9$%]+", title.lower())
    return [w for w in words if w not in _STOP]


def translate_title(title: str) -> str:
    """Rough deterministic EN→ZH translation for quick browsing.

    Known finance/AI terms map via glossary; tickers/numbers/unknown words
    are kept as-is. Result is a readable gloss, not a professional translation.
    """
    lower = title.lower()
    out = lower
    for phrase, zh in sorted(_GLOSSARY.items(), key=lambda kv: -len(kv[0])):
        out = re.sub(rf"\b{re.escape(phrase)}\b", zh, out)
    # drop possessive 's and punctuation noise, keep tickers
    out = out.replace("'s", "")
    out = re.sub(r"\$([A-Za-z]{1,6})", r"\1", out)
    words = []
    for w in out.split():
        w2 = re.sub(r"[^A-Za-z0-9%$.\u4e00-\u9fff-]+", "", w)
        if not w2:
            continue
        w2 = w2.strip("-.")
        if not w2:
            continue
        if w2.lower() in _STOP:
            continue
        words.append(w2)
    return " ".join(words) if words else lower


def _zh_tokens(title: str) -> List[str]:
    """Tokens for the topic label: translated Chinese words + entity names.

    Entities = capitalized words in the original (GXS, Grab, Singapore, FN...).
    Chinese words = glossary hits. Together they form a readable topic like
    'GXS 银行推出返现卡 新加坡'. Untranslated common English is dropped.
    """
    lower = title.lower()
    out = lower
    for phrase, zh in sorted(_GLOSSARY.items(), key=lambda kv: -len(kv[0])):
        out = re.sub(rf"\b{re.escape(phrase)}\b", zh, out)

    cjk = []
    for w in out.split():
        if any("\u4e00" <= ch <= "\u9fff" for ch in w):
            cjk.append(w)

    # strip source-suffix (' - Reuters', ' | X', ' — Y') before entity scan
    body = re.split(r"\s[-–—|]\s|[-–—|]\s*$", title)[0]

    # entities: capitalized words in the headline body (2+ chars, letters only)
    # that are NOT sentence-initial common words (e.g. 'The', 'And')
    entities = []
    _NOT_ENTITY = {"dw", "com", "the", "and", "priciest", "annual", "debut",
                   "finance", "global", "first", "new", "record", "best",
                   "bank", "launches", "launched", "launch", "cashback",
                   "credit", "card", "with", "rewards", "targets", "targeted",
                   "raises", "raised", "raise", "warns", "warn", "driven",
                   "stock", "stocks", "market", "markets", "valuation",
                   "capital", "capex", "boom", "continues", "ai", "sees",
                   "gains", "losses", "jumps", "falls", "rises", "hits",
                   "tops", "says", "said", "reports", "reported", "plans",
                   "planned", "sets", "nears", "heads", "eyes"}
    for m in re.finditer(r"\b([A-Z][A-Za-z]{1,12})\b", body):
        e = m.group(1)
        if e.lower() in _STOP or e.lower() in _NOT_ENTITY:
            continue
        entities.append(e)

    # interleave: entities first, then chinese gloss words (dedupe, cap)
    seen, tokens = set(), []
    for e in entities:
        if e.lower() not in seen:
            seen.add(e.lower())
            tokens.append(e)
    for c in cjk:
        if c not in seen:
            seen.add(c)
            tokens.append(c)
    return tokens[:8]


def extract_keywords(title: str, n: int = 4) -> List[str]:
    """Extract content keywords (known glossary terms + proper nouns)."""
    tokens = _tokenize(title)
    keywords = []
    seen = set()
    for t in tokens:
        if t in seen:
            continue
        seen.add(t)
        zh = _GLOSSARY.get(t)
        keywords.append(f"{t}{'(' + zh + ')' if zh else ''}")
        if len(keywords) >= n:
            break
    return keywords


def extract_topic_zh(title: str) -> str:
    """A short Chinese topic label for this exact post (theme, not theory).

    Only translated Chinese tokens + entity names are kept (e.g.
    'GXS 银行 推出 返现 卡'), so the label reads in Chinese instead of mixing
    English leftovers.
    """
    toks = _zh_tokens(title)
    if len(toks) >= 2:
        return " ".join(toks[:8])
    zh = translate_title(title)
    return " ".join(zh.split()[:8]) if zh else title[:40]


def topic_angles_zh(title: str, n: int = 3) -> Tuple[List[str], str]:
    """Precise Chinese angles anchored to THIS post's theme + keywords.

    The angle uses the SHORT topic core (first 3-4 words) so it reads
    naturally, plus a keyword line for full specificity.
    """
    topic = extract_topic_zh(title)
    topic_core = " ".join(topic.split()[:4]) if topic else "该事件"
    keywords = extract_keywords(title)
    kw_str = "、".join(keywords) if keywords else topic_core
    angles = []
    for i in range(n):
        angles.append(_ANGLE_ZH_TPL[i % len(_ANGLE_ZH_TPL)].format(topic=topic_core))
    return angles, kw_str


def enrich_zh(title: str) -> Dict[str, str]:
    """One-shot: returns {title_zh, topic_zh, keywords_zh, angles_zh}."""
    title_zh = translate_title(title)
    topic_zh = extract_topic_zh(title)
    angles_zh, kw_str = topic_angles_zh(title)
    return {
        "title_zh": title_zh,
        "topic_zh": topic_zh,
        "keywords_zh": kw_str,
        "angles_zh": angles_zh,
    }


def summarize_zh(title: str, source: str = "", category: str = "") -> str:
    """Chinese event summary for hot-topic tracking.

    Builds a readable Chinese gloss from the translated headline + topic +
    keywords, e.g. '事件摘要：GXS 银行与 Grab、Singtel 合作推出返现信用卡，
    属新加坡金融科技领域动态，建议关注其对本地数字支付竞争的影响。'
    """
    zh = translate_title(title)
    topic = extract_topic_zh(title)
    keywords = extract_keywords(title, n=3)
    cat_zh = {"ai": "AI", "fintech": "金融科技", "investing": "投资研究",
              "crypto": "数字金融", "general": "综合"}.get(category, "综合")
    src_note = f"，来源 {source}" if source else ""
    kw_note = f"；关键词：{'、'.join(keywords)}" if keywords else ""
    return (
        f"事件摘要：{zh}。"
        f"本条属{cat_zh}领域动态{src_note}，主题为「{topic}」{kw_note}。"
        f"建议结合原始来源核对数据后再跟进。"
    )
