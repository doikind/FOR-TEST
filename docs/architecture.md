# 架构说明

## 总体架构

单体应用：Streamlit 前端 + Python 业务逻辑 + SQLite 单文件存储。无前后端分离、无账号系统、无外部服务。两个 Agent 为**独立网页应用**（各自端口），共享一个 SQLite 数据库，各页面只显示自己 pipeline 的候选。

```
┌──────────────────────────────────────────────────────────┐
│  Agent 1 (app_agent1.py)        Agent 2 (app_agent2.py)   │
│  热点→候选池（采集/排序/画像/改编/审核） 拆解→创作（发现/拆解/生成/资产）│
└───────────────┬────────────────────────────┬────────────┘
                │                            │
        ┌───────▼─────────┐          ┌───────▼──────────┐
        │   agents/ 业务层  │          │   core/ 基础层    │
        │  collectors/     │          │  models/config/db│
        │  adaptation(改编) │          │  pipeline(去重/评分)│
        │  rewrite(改写)    │          │  follow(跟进判断)  │
        │  viral_breakdown  │          │  account(账号画像) │
        │  content_safety   │          │  authenticity     │
        │  review(审核)      │          │                  │
        │  feedback_model   │          │  SQLite (单文件)   │
        │  x_discovery      │          └──────────────────┘
        │  ai_provider      │
        └──────────────────┘
```

## 模块职责

| 模块 | 职责 |
|---|---|
| `core/models.py` | 统一 Event 数据模型 |
| `core/config.py` | 环境配置（.env 可选） |
| `core/authenticity.py` | 三标签常量（live_public/cached_public/simulated_demo） |
| `core/account.py` | 可编辑账号画像（多画像持久化、地区预设、相关性判断） |
| `core/db.py` | SQLite 幂等建表 + 存取 |
| `core/pipeline.py` | 标准化 → TF-IDF 去重 → 评分（含在线模型融合）→ 跟进判断 |
| `core/follow.py` | follow/consider/caution/skip 规则引擎（HN 社区分享降权） |
| `agents/collectors/` | Google News（官方媒体过滤+地区查询）/ GDELT / Hacker News / CoinGecko + 编排器 + 快照 |
| `agents/adaptation.py` | Agent1 文案改编引擎（不照搬原文） |
| `agents/rewrite.py` | 原创改写引擎（数字/事实织入，拆解洞察驱动结构） |
| `agents/x_discovery.py` | X 内容发现（nitter 多镜像 / x.com 页面 / FxTwitter 互动补全 / 快照兜底） |
| `agents/viral_breakdown.py` | 相对表现分数 + 六维度 + OBSERVED/INFERRED/UNKNOWN |
| `agents/viral_agent.py` | Agent2 主流程（拆解→模板→候选→资产库） |
| `agents/content_safety.py` | 金融风险信号 + LOW/MEDIUM/HIGH 分级 |
| `agents/similarity.py` | TF-IDF 余弦相似度（对标 + 历史候选） |
| `agents/review.py` | 五状态审核 + 审核日志 + 资产库 + 驳回分类 |
| `agents/feedback_model.py` | 在线学习反馈模型（SGD 逻辑回归，人工审核=监督信号） |
| `agents/ai_provider.py` | AI provider 抽象（缓存→模板→可选 OpenAI 兼容） |
| `scripts/evaluate_agents.py` | 三层可行性评估（mock + 快照 + 多路裁判） |

## 数据流

```
采集器(collectors，按画像地区生成查询) → Event 列表
  → pipeline.standardize（归一化标题、类目、去重键）
  → pipeline.dedupe（TF-IDF 余弦，阈值 0.82）
  → pipeline.score（热度×类目×时效×反馈因子，可解释）
     反馈因子 = 在线学习模型 P(approve)（样本≥10）或 规则权重（冷启动）
  → follow.annotate（跟进决策 + 理由，按账号画像计算相关性）
  → adaptation（Agent1 文案改编：主题/事实原子 → 原创英文）
  → review（五状态人工审核 + 审核日志 + 驳回分类）
  → 在线学习：Approve/Reject 记录样本 → 模型增量更新
  → asset（资产库 + 模拟发布 simulated_demo）

Agent2 侧：
  x_discovery（nitter/x.com/FxTwitter）→ viral_breakdown（拆解+证据分级）
  → 结构模板 → viral_agent（≥3 原创候选，相似度/风险检查）→ 资产库
```

## 关键设计决策

1. **数据真实性三标签**贯穿全链路，UI 全局徽标组件渲染
2. **AI provider 抽象**：业务层只依赖接口，缓存/模板/实时模型可替换，无 Key 可用
3. **改编/改写引擎**：文案不照搬原文——主题/事实原子提取 + 句式重构，TF-IDF 相似度复核
4. **人工审核唯一入口**：五状态机（含 Needs Revision 重新提交），Approve 才入库
5. **反馈在线学习**：人工采用/驳回即监督信号（SGD 逻辑回归），冷启动回退透明规则权重
6. **可编辑账号画像**：多画像持久化，地区/主题驱动采集查询与相关性判断
7. **评估闭环**：mock 故障注入 + 真实快照 + 5 路裁判，验证功能/数据/业务三层可行性
