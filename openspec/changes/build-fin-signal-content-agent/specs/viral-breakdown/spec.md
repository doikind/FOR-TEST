## Purpose

以 Finimize 为主要案例，基于其公开数据（公开帖子、公开互动指标或合规准备的真实公开数据快照），对比同一账号的高表现内容与普通内容，计算可解释的相对表现分数，从选题、Hook、结构、信息密度、CTA 与互动设计六个维度拆解差异，以 OBSERVED/INFERRED/UNKNOWN 标注证据等级，并沉淀可复用的内容结构模板。

## ADDED Requirements

### Requirement: 对标账号公开数据输入
系统 SHALL 以 Finimize 为主要对标案例，加载其 3 条相对高表现内容与 3 条普通内容的公开数据；AlphaSense 与 Hebbia SHALL 仅作为扩展参考，不纳入主对比；若 Finimize 真实公开数据不足，系统 MAY 按数据可得性切换为 AlphaSense 作为主案例。数据来源 MUST 为公开帖子、公开互动指标或合规准备的真实公开数据快照；仓库 MUST 避免大量保存完整 X 帖子，优先保存 Post ID、来源 URL、必要片段与派生特征；数据为模拟时 MUST 在 UI 明确标注 `simulated_demo`。

#### Scenario: 加载 Finimize 主案例
- **WHEN** 用户选择加载 Finimize 公开数据快照
- **THEN** 系统加载 3 条相对高表现与 3 条普通内容，每条含 Post ID、来源 URL、必要片段、派生特征与公开互动指标，并标注数据来源与真实性标签

#### Scenario: Finimize 数据不足切换
- **WHEN** Finimize 真实公开数据不足 6 条或关键指标缺失
- **THEN** 系统提示可切换为 AlphaSense 主案例，切换后重新执行对比分析

#### Scenario: 扩展参考不纳入主对比
- **WHEN** 用户查看 AlphaSense/Hebbia 扩展参考数据
- **THEN** 系统明确标注为"扩展参考"，不将其计入主案例的高表现/普通分组

#### Scenario: 导入自定义数据
- **WHEN** 用户导入 JSON/CSV 格式的账号数据
- **THEN** 系统解析并展示导入结果，保持"数据来源：用户导入"标识

### Requirement: 相对表现分数计算
系统 SHALL 计算每条内容的相对表现分数，MUST 考虑同一账号、相近时间范围、内容类型与公开互动指标（点赞、回复、转帖等），不得仅按点赞绝对值判断；表现分数 SHALL 可解释（展示计算因子）。

#### Scenario: 同账号相对对比
- **WHEN** 系统计算 Finimize 账号内内容表现
- **THEN** 每条内容获得相对表现分数，展示其在同账号、相近时间窗、同内容类型内的相对位置及因子明细

#### Scenario: 高表现与普通内容分组
- **WHEN** 系统依据相对表现分数划分内容组
- **THEN** 高表现组与普通组分别展示（主案例各 3 条），并标注分组阈值

### Requirement: 六维度拆解
系统 SHALL 按选题、Hook、结构、信息密度、CTA、互动设计六个维度对比高表现与普通内容，输出每个维度的差异观察与样本证据。

#### Scenario: 生成拆解报告
- **WHEN** 用户触发"拆解分析"
- **THEN** 系统输出六维度对比表：每个维度的高表现特征、普通内容特征与代表样本

### Requirement: 证据分级与归因审慎
系统 SHALL 为拆解结论标注证据等级：`OBSERVED`（从数据中直接观察到的差异）、`INFERRED`（系统推测的可能驱动因素）、`UNKNOWN`（当前数据无法证明）；系统 MUST NOT 将相关性描述为确定性因果关系，MUST 在输出驱动因素时同时说明其证据等级与局限。

#### Scenario: OBSERVED 结论
- **WHEN** 高表现内容与普通内容在某个维度存在可直接观察的差异（如长度、是否含数字、是否有 CTA 词）
- **THEN** 系统标注该结论为 OBSERVED 并附证据样本

#### Scenario: INFERRED 结论
- **WHEN** 系统推测某差异可能是表现驱动因素但无直接因果证据
- **THEN** 系统标注为 INFERRED 并注明"相关性≠因果"

#### Scenario: UNKNOWN 结论
- **WHEN** 数据不足以支持某维度判断（如缺乏互动数据）
- **THEN** 系统标注为 UNKNOWN 并说明缺失的数据

### Requirement: 结构模板沉淀
系统 SHALL 从拆解结果中提炼可复用的内容结构模板（选题模式、Hook 句式、结构框架、CTA 模式），并支持保存至内容资产库，模板 MUST 关联来源账号与表现依据。

#### Scenario: 保存可复用结构
- **WHEN** 用户确认某结构模板有价值
- **THEN** 模板以结构化形式保存到资产库，关联来源账号、证据等级与表现依据
