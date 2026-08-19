## 1. 初始化与数据层（P0）

- [x] 1.1 创建项目结构（app.py、core/、agents/、ui/、data/、data/snapshots/、data/simulated/、docs/）并编写 requirements.txt 与 .env.example
- [x] 1.2 初始化 SQLite（finsignal.db）：幂等建表 events/candidates/review_log/assets/accounts/posts/feedback_weights/ai_cache，含 data_authenticity 标签列与三标签常量

## 2. 数据采集层（P0）

- [x] 2.1 实现 Google News RSS 采集器（feedparser，主题限定 AI/fintech/investing，主要新闻发现）
- [x] 2.2 实现 GDELT 采集器（新闻覆盖与地区交叉验证，限定时间窗/关键词）
- [x] 2.3 实现 Hacker News 采集器（Firebase API：topstories → item 详情，AI 技术/开发者信号）
- [x] 2.4 实现采集编排器（每源独立 try/except、单源失败记录 warnings、产出 live_public 标准化事件）
- [x] 2.5 实现真实快照生成脚本（经真实接口采集写入 data/snapshots/，保留来源 URL/发布时间/采集时间）与快照加载器（实时失败提示切换，cached_public 标签，禁止静默伪装）

## 3. 热点处理管线（P0）

- [x] 3.1 实现事件标准化与去重（统一事件模型 + 归一化标题 + TF-IDF 余弦，阈值默认 0.82）
- [x] 3.2 实现优先级排序（热度 × 类目 × 时效 × 反馈校正，各因子单独计分，输出排序理由）
- [x] 3.3 实现跟进判断（follow / consider / caution / skip + 理由，风险关键词 → caution，促销/招聘/无关 → skip）
- [x] 3.4 实现事件摘要与内容角度生成（基于真实采集数据要点归纳 + 英文选题角度）

## 4. AI 生成与内容安全检查（P0）

- [x] 4.1 定义 AI provider 接口并实现 CacheProvider 与 TemplateProvider（无 Key 的 Demo 模式，缓存输出标注"AI 输出缓存"）
- [x] 4.2 实现内容安全检查（八类信号识别 + TF-IDF 余弦相似度 + LOW/MEDIUM/HIGH(Blocked) 等级判定）

## 5. 爆款拆解（P0，Finimize 主案例）

- [x] 5.1 整理 Finimize 公开数据（3 条相对高表现 + 3 条普通，Post ID/来源 URL/必要片段/派生特征/公开指标，不存完整帖子）
- [x] 5.2 实现相对表现分数、高/普通分组、六维度拆解、OBSERVED/INFERRED/UNKNOWN 证据分级与结构模板沉淀

## 6. 二次创作（P0）

- [x] 6.1 实现基于真实市场洞察 + 拆解洞察生成 ≥3 条原创英文候选（角度/互动目标/正文/Hook/结构/CTA/来源/风险/相似度完整字段）

## 7. 审核与内容资产库（P0）

- [x] 7.1 实现候选入池（topic_key 唯一、五状态）+ 人工审核（Approve/Reject/Needs Revision 填原因与意见）+ review_log 决策记录
- [x] 7.2 实现内容资产库（仅 Approved 入库、Blocked 禁止、模拟发布人工确认、simulated_demo 标识、复盘摘要）

## 8. Streamlit UI（P0）

- [x] 8.1 搭建骨架（多 tab + 全局真实性徽标组件 + 常显免责声明）
- [x] 8.2 热点发现页（采集按钮、来源状态/失败原因、事件列表、去重数量、优先级/排序理由、跟进判断）
- [x] 8.3 爆款拆解与二次创作页（高/普通对照、六维度、证据分级、≥3 条候选、相似度/风险结果）
- [x] 8.4 待审核池与资产库页（五状态操作、审核记录、模拟发布、simulated_demo 标识、复盘）

## 9. Demo 验证与交付（P0）

- [x] 9.1 端到端 + 边界测试（单源失败降级、全实时源失败走快照、无 Key 可跑、Blocked 禁止入库、模拟标识可见）
- [x] 9.2 编写 README + 数据来源/架构/AI 使用/人工审核点/局限/优化方向
- [x] 9.3 一键启动验证（pip install -r requirements.txt + streamlit run app.py）+ 端到端走查

## 10. 降级项（P1，不影响 P0 闭环，可延后或砍掉）

- [x] 10.1 实现 OpenAICompatProvider（OpenAI 兼容 API 适配层，有 Key 时实时增强，无 Key 回退模板/缓存）
- [x] 10.2 实现 CoinGecko 可选补充采集器（Crypto/数字金融事件，失败不影响主流程）
- [x] 10.3 实现反馈规则权重调整（采用 +0.05 / 驳回 -0.03，范围 -0.10~+0.10，UI 展示权重变化；若影响 P0 则仅保留 7.1 决策记录）
- [x] 10.4 整理 AlphaSense/Hebbia 扩展参考数据 + Finimize 数据不足时切换 AlphaSense 主案例
