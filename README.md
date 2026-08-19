# FinSignal Content Agent

> AI 金融内容候选系统 · 面向东南亚英文市场（新加坡为中心）
> 两个独立 Agent：**每日热点 → 候选内容池** 与 **爆款拆解 → 二次创作**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](#)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)](#)
[![SQLite](https://img.shields.io/badge/storage-SQLite-003B57)](#)
[![scikit-learn](https://img.shields.io/badge/ml-scikit--learn-F7931E)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](#)

FinSignal Content Agent 从**真实公开数据**出发，为关注 AI / 金融科技 / 投资研究的普通投资者（欧美、东南亚市场）生成英文 X 内容候选。系统强调**真实数据、完整闭环、产品判断、人工审核、可运行可演示**——不是套一个大模型聊天框。

> ⚠️ **重要**：本系统只提供内容辅助，**不构成投资建议**。所有内容需人工审核，不自动发布、不接真实 X 发布。

---

## ✨ 核心特性

### 🤖 Agent 1 · 每日热点 → 候选内容池
- 多源真实采集（Google News RSS / GDELT / Hacker News，CoinGecko 可选补充），**官方媒体过滤**（三级来源白名单 + `[官方]/[媒体]` 标注）
- 事件去重（TF-IDF 余弦）→ 优先级排序（热度/时效/类目/反馈因子，可解释）
- **可编辑账号画像**（多画像保存/切换，地区关键词自动生成），相关性判断按画像实时生效
- 中文翻译 + 精确主题/关键词/角度 + **改编引擎**（原创英文文案，不照搬原文）
- 五状态人工审核（Draft → Needs Revision → Pending Review → Approved / Rejected），修改意见持久化
- **在线学习反馈模型**（SGD 逻辑回归，人工采用/驳回即监督信号，冷启动回退规则权重）

### 🎯 Agent 2 · 爆款拆解 → 二次创作
- X 内容发现（nitter 多镜像 / x.com 页面 / FxTwitter 互动补全，快照兜底）
- 同账号高表现 vs 普通筛选（**相对表现分数**，非点赞绝对值；金融/AI 主题门槛）
- 六维度拆解（选题/Hook/结构/信息密度/CTA/互动设计）+ OBSERVED/INFERRED/UNKNOWN 证据分级
- **拆解洞察驱动正文结构**（高表现特征实际改写 Hook/CTA）
- ≥3 条原创英文候选（数字/事实织入正文，相似度含历史候选维度）
- 结构模板沉淀 → **一键应用复用**闭环；模拟发布表现规则化预估

### 🔗 共享能力
- 内容资产库（未处理/已完成/已删除三分组，批量操作）
- 金融风险检查（7 类信号，LOW/MEDIUM/HIGH，HIGH 禁入库）
- 模拟数据全链路 `simulated_demo` 标识，常显免责声明

---

## 🚀 快速开始

```bash
# Windows PowerShell
pip install -r requirements.txt

# Agent 1 · 每日热点 → 候选内容池
streamlit run app_agent1.py --server.port 8501

# Agent 2 · 爆款拆解 → 二次创作
streamlit run app_agent2.py --server.port 8502
```

浏览器打开：

| 应用 | 地址 | 作用 |
|---|---|---|
| **Agent 1（公网）** | https://doikind-finsignal-agent1.streamlit.app | 每日热点 → 候选内容池 |
| **Agent 2（公网）** | https://doikind-finsignal-agent2.streamlit.app | 爆款拆解 → 二次创作 |
| **Agent 1（本地）** | http://localhost:8501 | 每日热点 → 候选内容池 |
| **Agent 2（本地）** | http://localhost:8502 | 爆款拆解 → 二次创作 |
| 启动器（可选） | http://localhost:8500 | 导航页 |

> 本地双端口运行时，两个 Agent 可以共享一个 SQLite（`finsignal.db`）。分别部署到 Streamlit Community Cloud 后，两个应用位于独立运行环境，本地 SQLite 数据不会自动互通。

### 无 API Key 的 Demo 模式

系统**无需任何 API Key** 即可完整运行：
- 内容生成走**改编/模板引擎**（标注生成方式），绝不冒充实时模型调用
- 采集、去重、评分、风险检查、审核、存储全部真实运行
- 配置 `OPENAI_API_KEY` 后可启用 OpenAI 兼容适配层（可选增强）

复制 `.env.example` 为 `.env`（全部键可选）。

---

## 🏗️ 架构概览

```
┌──────────────────────────────────────────────────────┐
│  Agent 1 (app_agent1.py)      Agent 2 (app_agent2.py) │
│  热点→候选池                   爆款拆解→二次创作         │
└───────────────┬──────────────────────────┬───────────┘
                │                          │
        ┌───────▼─────────┐      ┌─────────▼──────────┐
        │  agents/ 业务层  │      │  core/ 基础层       │
        │  collectors      │      │  models/config/db  │
        │  adaptation      │      │  pipeline(去重/评分) │
        │  rewrite         │      │  follow(相关性判断)  │
        │  viral_breakdown │      │  account(画像)      │
        │  content_safety  │      │                    │
        │  review          │      │  SQLite            │
        │  feedback_model  │      └────────────────────┘
        └──────────────────┘
```

详细架构见 [`docs/architecture.md`](docs/architecture.md)。

---

## 🧪 三层可行性评估

系统内置评估脚本 `scripts/evaluate_agents.py`，用 **mock 工具 + 沙盒快照 + 多路裁判** 判断两个 Agent 是否可行：

```bash
python scripts/evaluate_agents.py
```

| 层 | 手段 | 验证 |
|---|---|---|
| **L1 确定性** | mock 固定样本 + 故障注入（单源/全源失败、无 Key） | 功能可行、降级正确、不伪造 |
| **L2 真实性** | 仓库真实快照离线复现 | 数据链路完整 |
| **L3 多路裁判** | 相关性/合规/原创性/结构/价值 5 裁判独立打分 | 业务质量（均分 ≥3.5 判定可行） |

---

## 📚 文档

| 文档 | 内容 |
|---|---|
| [架构说明](docs/architecture.md) | 模块职责、数据流、关键设计决策 |
| [数据来源说明](docs/data-sources.md) | 真实数据源、真实性标签、快照兜底、X 内容获取 |
| [AI 使用说明](docs/ai-usage.md) | Provider 抽象、缓存/模板/实时模式、无 Key Demo |
| [人工审核点说明](docs/human-review.md) | 五状态机、风险等级与审核关系、记录内容 |
| [3 分钟演示脚本](docs/demo-script.md) | 17 步 Demo 验收流程 |
| [GitHub 提交前安全检查](docs/github-safety.md) | 敏感信息、数据合规、提交清单 |

---

## 📂 目录结构

```
finsignal-content-agent/
├── app.py                  # 启动器（导航页）
├── app_agent1.py           # Agent 1 · 每日热点 → 候选池
├── app_agent2.py           # Agent 2 · 爆款拆解 → 二次创作
├── cli.py                  # CLI（采集/快照）
├── core/                   # 模型、配置、SQLite、管线、账号画像、跟进判断
├── agents/                 # 采集器、改编、改写、拆解、风险、审核、在线学习模型
├── ui/                     # UI 公共组件（真实性徽标、免责声明）
├── scripts/                # 依赖引导、三层评估
├── data/
│   ├── snapshots/          # 真实公开数据快照（cached_public）
│   └── simulated/          # 脱敏模拟数据（simulated_demo）
├── docs/                   # 说明文档
├── openspec/               # OpenSpec 规划工件
├── requirements.txt
└── .env.example
```

---

## ⚠️ 已知局限

- 无 X API，不接真实 X 发布；公开互动指标依赖 FxTwitter/nitter，可用性随公共镜像波动
- nitter 公共镜像经常被封换域名，实时发现失败时自动回退仓库快照
- 无 API Key 时内容由改编/模板引擎生成，质量有上限
- 在线学习模型需 ≥10 条审核样本才接管排序（冷启动期用规则权重）

## 🗺️ 后续优化方向

- 接入真实 OpenAI 兼容模型增强改编质量
- 更多地区预设与来源白名单
- Agent1/Agent2 打通（拆解模板 → 热点候选生成）
- 在线学习模型增加特征（情绪、选题角度）与时效衰减

---

## 🔒 安全与合规

- **免责声明**：所有页面常显 "This content is for informational purposes only and does not constitute investment advice."
- **不自动发布**：任何内容仅人工 Approve 后进入资产库；不接真实 X 发布
- **模拟数据标识**：互动指标/模拟发布表现一律 `simulated_demo`
- **数据合规**：不保存完整 X 帖子，仅 Post ID/URL/片段/派生特征；不声称拥有非公开指标
- 提交前检查见 [`docs/github-safety.md`](docs/github-safety.md)
