## Why

求职笔试需完成第2题（每日热点到候选内容池）与第5题（爆款内容拆解与二次创作）两道题，周四交付。当前项目没有可运行的内容中台：热点靠人工刷屏、爆款经验散落在个人记忆、候选内容无审核与沉淀流程。本项目用 2 天构建 FinSignal Content Agent——一个可本地运行、可现场演示的 AI 金融内容候选系统：以真实公开数据驱动"热点发现 → 内容创作 → 风险检查 → 人工审核 → 资产沉淀 → 反馈优化"完整业务闭环，面向东南亚英文市场（新加坡为中心）的 AI 金融出海品牌账号，为关注 AI、金融科技、投资研究的普通投资者产出英文 X 内容候选。

## What Changes

- 新增 **FinSignal Content Agent**：Python + Streamlit + SQLite 单体应用，本地一键运行（`pip install -r requirements.txt` + `streamlit run app.py`）。
- 新增**热点发现管线**（题目2）：从三类真实公开来源（Google News RSS、GDELT、Hacker News 官方 API，CoinGecko 仅作为 Crypto/数字金融事件的可选补充源，不开发其他连接器）采集热点事件 → 数据标准化 → 事件去重 → 优先级排序 → 跟进判断（是否值得目标账号跟进）→ 生成事件摘要、内容角度与英文候选内容。
- 新增**数据真实性标签体系**：每条采集数据必须携带 `live_public`（实时公开）/ `cached_public`（真实公开快照）/ `simulated_demo`（脱敏模拟）标签；快照兜底必须通过真实接口采集生成、保留来源 URL/发布时间/采集时间、标注 `cached_public`、实时失败时提示用户切换、禁止静默伪装成实时数据；单个来源失败时系统不伪造新闻、继续处理其他来源、UI 展示失败来源与原因。
- 新增**爆款拆解器**（题目5）：以 Finimize 为主要案例（3 条相对高表现 + 3 条普通内容），AlphaSense 与 Hebbia 仅作扩展参考；若 Finimize 真实公开数据不足，可按数据可得性切换 AlphaSense。基于公开帖子与公开互动指标（或合规真实快照）对比高表现与普通内容，拆解选题/Hook/结构/信息密度/CTA/互动设计 6 维度，输出 OBSERVED / INFERRED / UNKNOWN 三级证据判断，沉淀可复用结构模板；不接 X 登录、不抓私密数据、不声称拥有非公开指标，仓库只保存 Post ID、来源 URL、必要片段与派生特征。
- 新增**二次创作器**：围绕同一真实市场洞察生成 ≥3 条原创英文 X 候选，每条含内容角度、目标互动行为、英文正文、Hook 说明、结构、CTA、事实来源、风险提示与相似度检查结果；不照搬对标原句、不做空洞 AI 宣传。
- 新增**内容安全与风险检查**：识别未经证实消息、缺少来源的事实陈述、保证收益、确定性价格预测、直接荐股/投资指令、敏感地区问题、与对标高度相似、抄袭风险连续表达，输出 LOW / MEDIUM / HIGH 风险等级；LOW 允许进入人工审核但不自动批准，MEDIUM 必须修改并重新检测，HIGH 为 Blocked 禁止进入 Approved 与资产库；UI 常显免责声明（"This content is for informational purposes only and does not constitute investment advice."）。
- 新增**人工审核流程**：候选状态 Draft → Needs Revision → Pending Review → Approved / Rejected，任何内容不自动发布，仅人工 Approve 后进入内容资产库；记录审核动作、时间、驳回原因与修改意见。
- 新增**反馈优化**：不训练模型，采用透明规则权重调整——采用 +0.05、驳回 -0.03，累计范围限制在 -0.10 ~ +0.10，不得称为模型训练或 AI 自学习；若影响 P0 进度则降级为 P1（仅保留决策记录）；模拟发布表现一律标注 `simulated_demo`，不得描述为真实运营成绩。
- 新增**内容资产库**：已批准内容、可复用结构模板、采用/驳回/模拟表现记录统一沉淀。
- 技术约束：不引入 LangChain/CrewAI 等重型框架，普通 Python 函数 + 清晰工作流；scikit-learn TF-IDF + 余弦相似度做内容相似度检查；AI 生成封装为独立 provider 接口（无 Key 的 Demo 模式 + 缓存 AI 输出 + 可选 OpenAI 兼容适配层），AI 输出缓存明确标注，不冒充现场实时模型调用。
- 明确不做：登录、权限、定时任务、真实 X 发布、多账号监控、模型训练、Docker、云数据库、多 Agent 框架、复杂图表、额外数据源连接器。

## Capabilities

### New Capabilities

- `hot-topic-discovery`: 从 Google News RSS、GDELT、Hacker News API 三类真实公开来源（CoinGecko 可选补充）采集热点事件，完成数据标准化、事件去重、优先级排序、跟进判断与事件摘要/内容角度生成，全部数据携带真实性标签并支持快照回退。对应题目2前半段。
- `content-safety`: 对事件与候选内容执行金融内容安全与合规检查，按确定性触发规则识别八类风险信号并输出 LOW/MEDIUM/HIGH（Blocked）等级，HIGH 禁止进入 Approved 与资产库。横切于热点与创作两条管线。
- `viral-breakdown`: 以 Finimize 为主要案例（AlphaSense/Hebbia 扩展参考），对比高表现与普通内容，按 6 维度拆解并以 OBSERVED/INFERRED/UNKNOWN 标注证据等级，沉淀可复用结构模板。对应题目5前半段。
- `content-creation`: 围绕同一真实市场洞察生成 ≥3 条原创英文 X 候选（角度/互动目标/正文/Hook/结构/CTA/来源/风险/相似度），执行 TF-IDF 余弦相似度检查，写入待审核池。对应题目5后半段。
- `content-pool-review`: 统一待审核内容池，五状态人工审核（Draft/Needs Revision/Pending Review/Approved/Rejected），记录审核动作与原因，透明规则权重调整并在 UI 展示。两题闭环的汇合点。
- `asset-library`: 内容资产库：已批准内容、可复用结构模板、采用/驳回记录与模拟发布表现追踪，所有模拟数据以 `simulated_demo` 明确标识。支撑复盘闭环。

### Modified Capabilities

（无。全新项目，无既有 spec 需要修改。）

## Impact

- **代码**：新项目 `finsignal-content-agent/`，含 Streamlit 应用入口、数据源采集模块、管线处理模块、AI provider 抽象层、SQLite 存储层、真实公开数据快照与脱敏模拟数据。
- **依赖**：Python 3.10+；`streamlit`、`requests`/`httpx`、`feedparser`、`pandas`、`scikit-learn`（TF-IDF/余弦相似度）、`sqlite3`（标准库）；可选 OpenAI 兼容 SDK（有 Key 时启用，无 Key 走 Demo 缓存/模板模式）。
- **数据**：SQLite 单文件 `finsignal.db`（events / candidates / review_log / assets / accounts / posts / feedback_weights / ai_cache 等表 + 种子数据）；`data/snapshots/` 保存真实公开数据快照（cached_public），`data/simulated/` 保存脱敏模拟数据（simulated_demo）。
- **外部系统**：Google News RSS、GDELT、Hacker News Firebase API、CoinGecko 公开 API（可选补充）；无 X API、无真实发布、无登录。
- **安全/合规**：所有账号操作（采用、驳回、模拟发布）仅人工触发；不采集隐私数据；金融内容候选自动附加免责声明；AI 输出缓存明确标注；模拟数据与真实数据严格区分。
- **交付物**：可运行代码、requirements.txt、README.md、.env.example、真实公开数据快照、脱敏模拟数据、数据来源说明、架构说明、AI 使用说明、人工审核点说明、当前局限、后续优化方向、3 分钟 Demo 演示脚本、GitHub 提交前安全检查说明。
