"""我方账号画像 + 相关性判断。

假设一个金融 AI 推广账号（FinSignal），面向东南亚英文市场（新加坡为中心），
为关注 AI / 金融科技 / 投资研究的普通投资者提供内容。相关性判断用于决定
某条热点是否值得我方账号跟进。

账号画像是可编辑的：设置页可保存自定义画像到 data/account_profile.json，
relevance_score 优先使用自定义画像，未配置时回退默认。
"""
import json
import os

from core import config

# --- 账号画像 -----------------------------------------------------------------

ACCOUNT_PROFILE = {
    "name": "FinSignal",
    "positioning": "AI 金融出海品牌账号（面向东南亚英文市场，新加坡为中心）",
    "target_users": "欧美/东南亚的普通投资者 + 关注 AI 金融产品的用户",
    "voice": "专业品牌口吻 + 开发者口吻",
    "language": "英文为主（X 内容），中文辅助（内部审阅）",
    "core_topics": ["ai", "fintech", "investing"],      # 核心主题（高相关）
    "secondary_topics": ["crypto"],                     # 次级主题（中等相关）
    "regions": ["Singapore"],  # 默认主地区（与 REGION_PRESETS 键一致）
}

# 相关性关键词（用于标题命中判断）
TOPIC_KEYWORDS = {
    "ai": ("ai", "artificial intelligence", "llm", "openai", "anthropic", "model",
           "machine learning", "agentic", "deepmind", "gpt", "genai"),
    "fintech": ("fintech", "payment", "bank", "digital bank", "wallet", "neobank",
                "remit", "lending", "stablecoin", "cbdc"),
    "investing": ("invest", "market", "stock", "fund", "etf", "trading", "valuation",
                  "ipo", "earnings", "merger", "acquisition", "capital", "funding"),
    "crypto": ("crypto", "bitcoin", "ethereum", "blockchain", "defi", "token", "coin"),
}

REGION_KEYWORDS = {
    "singapore": ("singapore", "sg", "mas", "gxs", "revolut singapore", "shopee"),
    "southeast_asia": ("southeast asia", "asean", "malaysia", "indonesia", "thailand",
                       "vietnam", "philippines"),
}

# Region presets: pick a region by name → keywords are generated automatically.
REGION_PRESETS = {
    "Singapore": ("singapore", "sg", "mas", "gxs", "revolut singapore", "shopee", "uob", "dbs", "ocbc"),
    "Philippines": ("philippines", "manila", "peso", "bsp", "gcash", "maya", "unionbank", "bdo", "philippine"),
    "Indonesia": ("indonesia", "jakarta", "rupiah", "bca", "gopay", "ovo", "bank indonesia", "bi"),
    "Malaysia": ("malaysia", "kuala lumpur", "ringgit", "bnm", "grab malaysia", "maybank"),
    "Thailand": ("thailand", "bangkok", "baht", "bot", "kbank", "scb", "true money"),
    "Vietnam": ("vietnam", "hanoi", "ho chi minh", "dong", "sbf", "momo", "vpbank"),
    "Southeast Asia (general)": ("southeast asia", "asean", "malaysia", "indonesia", "thailand",
                                 "vietnam", "philippines", "singapore"),
    "US": ("us", "usa", "federal reserve", "sec", "nasdaq", "nyse", "wall street", "treasury"),
    "China": ("china", "beijing", "shanghai", "yuan", "pboc", "alibaba", "tencent", "chinese"),
    "Japan": ("japan", "tokyo", "yen", "boj", "nikkei", "softbank", "japanese"),
    "Europe": ("europe", "euro", "ecb", "frankfurt", "london", "eu", "germany", "france"),
    "Global": ("global", "world", "international", "cross-border"),
}

# ---- editable account profile -------------------------------------------------
_PROFILE_DIR = os.path.join(config.BASE_DIR, "data", "profiles")
_CURRENT_FILE = os.path.join(_PROFILE_DIR, "_current.txt")


def _profile_path(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    return os.path.join(_PROFILE_DIR, f"{safe}.json")


def list_profiles() -> list:
    """Names of all saved profiles (sorted)."""
    if not os.path.isdir(_PROFILE_DIR):
        return []
    names = []
    for f in os.listdir(_PROFILE_DIR):
        if f.endswith(".json") and not f.startswith("_"):
            names.append(f[:-5])
    return sorted(names)


def current_profile_name() -> str:
    if os.path.exists(_CURRENT_FILE):
        with open(_CURRENT_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() or "FinSignal"
    return "FinSignal"


def set_current_profile(name: str) -> None:
    os.makedirs(_PROFILE_DIR, exist_ok=True)
    with open(_CURRENT_FILE, "w", encoding="utf-8") as f:
        f.write(name)


def load_profile(name: str | None = None) -> dict:
    """Return a saved profile (or the currently active one, or default)."""
    if name is None:
        name = current_profile_name()
    path = _profile_path(name)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = dict(ACCOUNT_PROFILE)
            merged.update(data)
            merged.setdefault("name", name)
            return merged
        except Exception:  # noqa: BLE001
            pass
    # fall back to default FinSignal
    merged = dict(ACCOUNT_PROFILE)
    merged["name"] = name if name and name != "FinSignal" else merged["name"]
    return merged


def save_profile(profile: dict, name: str | None = None) -> str:
    """Persist a profile by name and set it current. Returns the name."""
    name = name or profile.get("name") or "FinSignal"
    os.makedirs(_PROFILE_DIR, exist_ok=True)
    with open(_profile_path(name), "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    set_current_profile(name)
    return name


def delete_profile(name: str) -> None:
    path = _profile_path(name)
    if os.path.exists(path):
        os.remove(path)
    if current_profile_name() == name:
        set_current_profile("FinSignal")


def reset_profile() -> None:
    """Back to defaults (remove active profile, keep others)."""
    name = current_profile_name()
    delete_profile(name)


def relevance_score(ev, profile: dict | None = None) -> dict:
    """Compute topic + region relevance for the brand account.

    Returns {score (0..1), topics, regions, reasons}.

    Region keywords come from the profile (editable), defaulting to the
    built-in REGION_KEYWORDS — so changing the account's target region (e.g.
    Singapore → Philippines) actually changes which regions hit.
    """
    profile = profile or load_profile()
    title = (ev.title or "").lower()
    category = ev.category or "general"
    core_topics = profile.get("core_topics") or ["ai", "fintech", "investing"]
    # region keywords: from the profile, else built-in presets (keys like 'Singapore')
    region_keywords = profile.get("region_keywords") or REGION_PRESETS
    topics_hit = []
    regions_hit = []
    reasons = []

    # 1. topic relevance
    for topic, toks in TOPIC_KEYWORDS.items():
        if any(t in title for t in toks):
            topics_hit.append(topic)
    if category in core_topics:
        if category not in topics_hit:
            topics_hit.append(category)

    # 2. region relevance (driven by the editable account profile)
    for region, toks in region_keywords.items():
        if any(t in title for t in toks):
            regions_hit.append(region)

    # 3. score: topic (core=1.0 / secondary=0.7 / none=0.3), region bonus
    topic_score = 0.3
    if topics_hit:
        core_hit = any(t in core_topics for t in topics_hit)
        topic_score = 1.0 if core_hit else 0.7
    region_score = 0.2 if regions_hit else 0.0

    score = round(min(1.0, topic_score * 0.8 + region_score * 0.2), 3)
    reasons = []
    if topics_hit:
        reasons.append(f"命中主题 {topics_hit}")
    if regions_hit:
        reasons.append(f"命中地区 {regions_hit}")
    if not topics_hit and not regions_hit:
        reasons.append("未命中账号主题/地区关键词")

    return {"score": score, "topics": topics_hit, "regions": regions_hit, "reasons": reasons}


def is_worth_following(ev, profile: dict | None = None) -> bool:
    """Shortcut: is this event worth the account following (relevance >= 0.5)."""
    return relevance_score(ev, profile)["score"] >= 0.5
