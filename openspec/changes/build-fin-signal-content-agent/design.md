## Context

全新单体应用（此前 FastAPI 原型已弃用，不在交付范围）。约束见 proposal.md：Python + Streamlit + SQLite、热点发现与爆款拆解两线合并闭环、三类真实公开数据源（Google News RSS + GDELT + Hacker News，CoinGecko 仅可选补充）、数据真实性三标签、无 API Key 可完整运行、所有账号操作人工确认、不接真实 X 发布、不购买 X API、不引入 LangChain/CrewAI 等重型框架。技术选型追求"少依赖、低风险、快演示"，用普通 Python 函数 + 清晰工作流实现。

## Goals / Non-Goals

**Goals:**
- 单一 Streamlit 进程内完成采集 → 标准化 → 去重 → 排序 → 跟进判断 → 内容生成 → 内容安全检查 → 审核 → 资产 → 复盘全闭环
- SQLite 单文件持久化，零外部服务，`pip install -r requirements.txt` + `streamlit run app.py` 即可运行
- 数据真实性标签（live_public / cached_public / simulated_demo）贯穿采集、存储、UI 全链路；快照兜底通过真实接口生成，绝不静默伪装成实时
- 无 API Key 时系统完整可用（缓存 AI 输出 + 模板降级），有 Key 时经 OpenAI 兼容适配层增强
- 所有"账号操作"（采用/驳回/模拟发布）只允许人工触发
- 演示可离线兜底：公开源全挂时可切换到仓库内真实快照继续演示

**Non-Goals:**
- 不接真实 X API、不真实发布、不自动互动（模拟发布仅人工录入表现）
- 不做登录/权限/多租户（单机演示）
- 不做定时调度系统、不做多账号监控
- 不训练机器学习模型（第一版只用透明规则权重调整，不得称"模型训练/自学习"）
- 不做 Docker/云数据库/多 Agent 框架/复杂图表
- 不开发数据源之外的连接器（仅 Google News RSS、GDELT、Hacker News、CoinGecko 可选）

## Decisions

### D1: Streamlit 作为唯一前端与运行入口
- **选择**：Streamlit 单页多 tab（热点发现 / 内容创作 / 爆款拆解 / 待审核池 / 内容资产库 / 复盘与反馈）。
- **理由**：交付 UI 成本最低，无需前后端分离；官方支持 `st.session_state` 管理交互态；演示时"人工确认点"可视化直观。
- **备选**：FastAPI + 前端（更灵活但工作量大）；纯 CLI（演示观感差，缺人工确认点可视化）。已弃用 FastAPI 原型。

### D2: SQLite + 标准库 sqlite3
- **表**：`events`（标准化事件：来源/标题/URL/发布时间/采集时间/真实性标签/类目/优先级/跟进判断）、`candidates`（候选内容：topic_key 唯一、来源管线、角度/正文/Hook/结构/CTA/来源/风险/相似度/状态/驳回原因/修改意见）、`review_log`（审核动作/时间/原因/意见）、`assets`（资产库：结构模板与已批准内容/状态/模拟表现 JSON/真实性标签）、`accounts`（对标账号）、`posts`（对标帖子元数据：Post ID/URL/片段/派生特征/公开指标，避免保存完整帖子）、`feedback_weights`（类目/特征权重与调整历史）、`ai_cache`（AI 输出缓存：输入哈希/输出/生成方式/时间）。
- **理由**：单文件、零部署、事务安全；符合本地部署要求。
- **备选**：JSON 文件（原型用过，并发与查询弱）；Postgres（过重，违背轻量约束）。

### D3: 数据源 = Google News RSS + GDELT + Hacker News + CoinGecko（可选补充）
- **选择**：`feedparser` 解析 Google News RSS（`https://news.google.com/rss/search?q=...`，主题限定 AI/fintech/investing，作为主要新闻发现）；GDELT 公开 API（新闻覆盖与地区交叉验证，验证事件是否为东南亚/新加坡相关及多来源覆盖）；`httpx`/`requests` 请求 Hacker News Firebase API（topstories → item 详情，AI 技术与开发者讨论信号）；CoinGecko 公开 API 仅作为 Crypto/数字金融事件的可选补充源。**不开发其他连接器**。
- **理由**：三类核心源覆盖"金融资讯（Google News RSS）、地区/覆盖交叉验证（GDELT）、AI 技术/开发者讨论（Hacker News）"，与账号定位（AI 金融出海、新加坡为中心）匹配；CoinGecko 仅在涉及 Crypto/数字金融事件时补充。
- **失败策略**：每源独立 try/except，单源失败仅记录 warnings 并继续；全部失败时 UI 提示用户切换加载 `data/snapshots/` 下真实公开快照（cached_public），快照由开发期经真实接口采集生成，绝不伪造新闻，绝不静默伪装成实时。
- **备选**：NewsAPI（需注册 Key）、X API（明令不买）、praw（需 Reddit Key）。均已排除。

### D4: 数据真实性标签 = 全局三值枚举
- **选择**：`data_authenticity ∈ {live_public, cached_public, simulated_demo}`，作为事件/候选/资产/表现的公共字段；采集器产出 `live_public`，快照加载产出 `cached_public`（保留来源 URL/发布时间/采集时间），预置演示账号与模拟表现产出 `simulated_demo`；Streamlit 用徽标/警告组件统一渲染。
- **理由**：满足"模拟数据必须明确标识"的硬性要求；快照兜底是演示离线保障，必须与实时数据可区分，禁止静默伪装。
- **备选**：仅布尔 `is_mock`（区分不了"实时公开/真实快照"两层真实数据，且快照回退正是演示兜底关键）。

### D5: 去重与相似度 = 归一化标题 + scikit-learn TF-IDF 余弦
- **选择**：事件去重用归一化标题相似度（TF-IDF + 余弦，阈值默认 0.82，可配置）；候选内容相似度检查同样用 TF-IDF + 余弦（对标帖子 + 历史候选语料），输出相似度分数与对标来源。
- **理由**：点名要求 scikit-learn 的 TF-IDF 与余弦相似度；小规模语料（每日 ≤ 100 事件、候选 ≤ 50 条）O(n²) 可接受，零额外基础设施。
- **备选**：纯字符串 SequenceMatcher（精度差，且不满足对 sklearn 的要求）；datasketch MinHash-LSH（万级才值得，依赖更重）。

### D6: 优先级与跟进判断 = 确定性规则引擎
- **选择**：`priority_score = 热度因子 × 类目匹配因子 × 时效因子 × 反馈校正因子`，各因子单独计分并展示明细（排序理由可解释）；跟进判断 follow/consider/caution/skip 由规则表驱动（风险关键词 → caution，促销/招聘/无关模式 → skip）。
- **理由**：确定性规则可复现、可解释（注重"判断逻辑清晰"），且无 Key 也可运行。
- **备选**：LLM 判断（不可复现、无 Key 不可用）。规则为主、LLM 增强为辅。

### D7: AI 生成 = 独立 Provider 接口 + 缓存 + 适配层
- **选择**：`ai_provider.py` 定义统一接口（`generate_candidates(event, angles, ...) -> list[CandidateDraft]`）；三个实现：`CacheProvider`（查 `ai_cache` 表，真实输入→缓存输出，标注"AI 输出缓存"）、`TemplateProvider`（无 Key 时的规则模板降级，标注"模板模式"）、`OpenAICompatProvider`（检测 `OPENAI_API_KEY`/兼容端点 env，OpenAI 兼容 API 适配层，标注"实时模型"）；按"缓存 → Key → 模板"顺序解析。业务管线只依赖接口，不感知具体实现。
- **理由**：无 Key 可完整演示；缓存不冒充实时调用；替换/扩展模型供应商零侵入。
- **备选**：业务代码直接调 SDK（耦合、无 Key 即瘫痪）；LangChain/CrewAI（明确不引入）。

### D8: 内容安全检查 = 确定性触发规则（content-safety）
- **选择**：`content_safety.py` 对每条候选执行八类信号识别：未经证实消息、缺少来源的事实陈述、保证收益、确定性价格预测、直接荐股/投资指令、敏感地区问题、与对标高度相似、抄袭风险连续表达；风险等级按确定性规则判定——**HIGH（Blocked）**：命中保证收益/确定性价格预测/直接荐股/敏感地区任一；**MEDIUM**：命中未经证实/缺来源/高相似/抄袭且未触发 HIGH，必须修改后重新检测；**LOW**：未命中任何信号，允许进入人工审核但不自动批准。相似度用 D5 的 TF-IDF 余弦（对标/历史比对 + 连续表达匹配）。
- **理由**：全部可解释、可离线运行；等级直接约束审核流程（HIGH Blocked 禁止进入 Approved 与资产库）。
- **备选**：LLM 风险审查（质量高但无 Key 不可用、不可复现）。规则为主、LLM 增强可留扩展位。

### D9: 爆款拆解 = Finimize 主案例 + 相对表现分数 + 证据分级
- **选择**：以 Finimize 为主案例，加载 3 条相对高表现 + 3 条普通内容的公开数据；AlphaSense/Hebbia 仅扩展参考不纳入主对比；Finimize 真实公开数据不足时切换 AlphaSense。同账号内按"相对表现分数"分组（分数 = 公开指标（点赞/回复/转帖）在相近时间窗、同内容类型内的标准化相对值，绝不单看点赞绝对值）；六维度特征用规则提取（长度、问句、数字、emoji、标签、CTA 词、结构段数等）；结论标注 OBSERVED（数据直接观察到）/ INFERRED（推测驱动因素，注明相关性≠因果）/ UNKNOWN（数据不足）；仓库保存 Post ID/URL/必要片段/派生特征，不存完整帖子。
- **理由**：可实现、可解释、合规（不抓私密数据、不声称拥有非公开指标）；避免黑箱 ML。
- **备选**：LLM 拆解（质量高但依赖 Key、不可复现）。规则为主、可选 LLM 增强。

### D10: 反馈优化 = 透明规则权重调整（不训练，可降级）
- **选择**：`feedback_weights` 表记录类目/特征权重及每次调整（调整前后值、触发动作、驳回原因归类）；采用 → 权重 +0.05，驳回 → -0.03，累计范围限制 -0.10 ~ +0.10（封顶后停止同向调整）；`priority_score` 实时读取最新权重，UI 展示调整前后对比；措辞上明确"规则权重调整"，**不得称为模型训练或 AI 自学习**。若影响 P0 进度，降级为仅记录决策（review_log 保留采用/驳回），暂不应用权重调整。
- **理由**：满足"不训练模型 + 规则权重调整 + 权重变化可见"；全部透明可解释；降级路径保住 P0 闭环。
- **备选**：训练轻量模型（超范围、黑箱、不现实）。

### D11: 模拟数据标识与免责声明
- **选择**：全局组件 `render_authenticity_badge()` 渲染真实性标签徽标；所有页面常显免责声明"This content is for informational purposes only and does not constitute investment advice."；模拟发布表现一律 `simulated_demo` 标注。
- **理由**：硬性要求；统一组件保证不漏标。

## Risks / Trade-offs

- [Google News RSS 返回结构/区域差异] → 主题参数限定 + 解析兼容多字段；失败走快照兜底。
- [GDELT API 返回量大/结构复杂] → 限定时间窗与关键词，只取前 N 条并做地区交叉验证；失败仅警告该源。
- [Hacker News API 偶发超时] → 短超时 + 单源降级，不阻塞其他源。
- [CoinGecko 限流（无需 Key 但高频 429）] → 仅可选补充源，失败不影响主流程；请求间隔 + 结果缓存。
- [Streamlit 交互态在 rerun 间丢失] → 关键状态全部持久化 SQLite；session_state 仅存临时 UI 状态。
- [TF-IDF 阈值误报/漏报] → 阈值可配置；相似度仅"标记"不阻断人工采用（人工确认优先）。
- [无 API Key 时内容质量偏模板化] → README 与演示话术明确"模板/缓存为降级模式，接入 Key 即增强"；缓存来自真实输入，演示时明确标注。
- [规则权重调整被误认为"模型学习"] → UI 与 README 明确"第一版不训练模型，采用透明规则权重调整"；必要时降级为仅记录决策。
- [Finimize 公开数据不足] → 设计切换路径（AlphaSense），主案例选择在实现期按数据可得性确认。
- [模拟表现被误认为真实成绩] → 全部 `simulated_demo` 徽标 + README 强调。
- [工期紧] → 严格按 tasks.md 分层推进：先跑通 P0 最小闭环，再增强（拆解、二次创作、复盘、快照）。

## Migration Plan

全新项目，无迁移需求。部署 = 安装依赖 + `streamlit run app.py`；SQLite 文件首次运行自动建表并写入种子数据（脱敏模拟账号 + 真实快照导入指引）；提供"重置数据库"按钮（或 `--reset-db` 启动参数）。GitHub 提交前检查：`.env` 不入库、仅提供 `.env.example`、`finsignal.db` 加入 `.gitignore`、快照数据检查无密钥/无隐私。

## Open Questions

（无阻塞性未知项。以下留待实现期确认，不影响 spec 与任务拆分：Finimize 与 AlphaSense 二者公开数据可得性在实现时实地验证并择一为主案例；OpenAI 兼容端点默认指向 OpenAI 还是 DeepSeek——由 `.env` 的 `OPENAI_BASE_URL` 决定，两者皆可。）
