# 数据来源说明

本系统使用**真实公开数据**，不生成假新闻。所有采集数据都保存：标题、来源、原始 URL、发布时间、采集时间、来源类别、数据真实性标签。

## 数据真实性标签

| 标签 | 含义 | 何时使用 |
|---|---|---|
| `live_public` | 实时公开数据 | 通过真实公开接口/RSS 实时采集 |
| `cached_public` | 真实公开数据快照 | 仓库内保存的、由真实接口采集生成的快照，实时失败时兜底 |
| `simulated_demo` | 脱敏模拟数据 | 演示用数据（如 Finimize 对标互动指标），绝不冒充真实 |

## 数据源

### 1. Google News RSS（主要新闻发现）
- 端点：`https://news.google.com/rss/search?q=...&hl=en-SG&gl=SG&ceid=SG:en`
- 主题：AI fintech / artificial intelligence investing / fintech Singapore / digital finance
- 无需注册密钥

### 2. GDELT（新闻覆盖与地区交叉验证）
- 端点：`https://api.gdeltproject.org/api/v2/doc/doc`
- 用途：验证事件是否为东南亚/新加坡相关及多来源覆盖
- 注意：免费接口对高频请求返回 429，失败时降级为快照

### 3. Hacker News API（AI 技术/开发者讨论信号）
- 端点：`https://hacker-news.firebaseio.com/v0/topstories.json` → item 详情
- 过滤：标题含 AI/LLM/fintech/investing 等主题 token
- 无需注册密钥

### 4. CoinGecko（可选补充，P1）
- 用途：Crypto/数字金融事件补充
- 默认关闭（`.env` 中 `SOURCE_COINGECKO=0`）

## 快照兜底

- 快照生成：`python cli.py snapshot`（经真实接口采集，写入 `data/snapshots/`）
- 快照加载：`python cli.py load` 或 UI「加载真实公开数据快照」按钮
- 快照**保留来源 URL、发布时间、采集时间**，加载时强制 `cached_public` 标签
- **禁止静默伪装**：快照数据绝不显示为 `live_public`

## Agent 2 · X 内容数据（真实公开数据）

**Agent 2 默认从 x.com 公开页面实时解析真实推文**（无需登录、无需 API、不抓私密数据）：

- 数据源：`https://x.com/<screen_name>`（如 Finimize）
- 获取字段：**真实 Post ID、来源 URL、推文全文、发布时间**（`created_at_ms`）
- 真实性标签：`live_public`
- 真实快照：`data/snapshots/x_finimize.json`（cached_public，离线兜底）

**关于互动指标（点赞/回复/转帖）**：
- x.com 公开页面对匿名访客**不渲染完整互动计数**（该数据属于 X 付费 API）
- 系统**不虚构互动数字**：相对表现分数基于**可观察派生特征**（长度、信息密度、emoji、列表结构、CTA）计算
- 互动数据标记为 **UNKNOWN**，在 UI 明确说明，绝不声称拥有非公开指标

**降级路径**：X 不可达（429/网络受限）时自动回退 `data/snapshots/x_finimize.json`（cached_public）或模拟数据（simulated_demo），并在 UI 明示原因。

## 模拟数据说明

`data/simulated/finimize_posts.json` 等是**脱敏模拟演示数据**（`simulated_demo`）：
- 仅用于 X 完全不可达时的最后兜底演示
- Post ID、来源 URL 为占位符；片段为改写后的派生特征
- 互动指标为模拟值，**绝不描述为真实运营成绩**
