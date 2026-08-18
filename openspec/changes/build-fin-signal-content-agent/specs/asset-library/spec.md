## Purpose

以内容资产库承载已批准内容、可复用结构模板、采用/驳回记录与模拟发布表现追踪，让"结构复用→表现"关系可复盘；所有模拟数据以 `simulated_demo` 明确标识，绝不把模拟结果描述为真实运营成绩。

## ADDED Requirements

### Requirement: 资产入库与状态流转
系统 SHALL 仅将人工批准（Approved）的候选内容存入资产库，状态按 draft → approved → published 流转；状态变更 MUST 仅由人工在 UI 触发；系统 MUST NOT 将未批准或 HIGH（Blocked）风险内容写入资产库。

#### Scenario: 已批准内容入库
- **WHEN** 用户在待审核池批准某候选
- **THEN** 该内容进入资产库并标记为 approved，记录批准时间与审核动作

#### Scenario: Blocked 内容禁止入库
- **WHEN** 某候选风险等级为 HIGH
- **THEN** 系统禁止其进入批准内容库，仅可查看或驳回

#### Scenario: 模拟发布预览与确认
- **WHEN** 用户对 approved 资产执行"模拟发布"预览
- **THEN** 系统展示发布预览（正文、来源、CTA、免责声明）并要求人工确认；确认后状态更新为 published 并记录发布时间

### Requirement: 模拟表现记录与标识
系统 SHALL 支持"模拟发布"后的表现录入（曝光、点赞、回复、转帖等公开指标字段）；所有模拟表现数据 MUST 标注为 `simulated_demo`，UI 显著标识"模拟数据"，MUST NOT 将模拟结果描述为真实运营成绩。

#### Scenario: 录入模拟表现
- **WHEN** 用户对 published 资产录入表现指标
- **THEN** 系统计算互动率并存储，数据真实性标签为 `simulated_demo`

#### Scenario: 模拟标识可见
- **WHEN** 用户查看资产库或复盘页面
- **THEN** 所有模拟数据均带"模拟数据"标识，与真实数据（live_public/cached_public）可区分

### Requirement: 资产检索与表现追踪
系统 SHALL 支持按来源、状态、结构模板、真实性标签检索资产，并按资产展示其表现历史（互动率、曝光等），支持与账号基准表现对比。

#### Scenario: 检索资产
- **WHEN** 用户按状态或模板筛选资产库
- **THEN** 系统返回匹配资产及其表现摘要

#### Scenario: 表现对比
- **WHEN** 用户查看某资产详情
- **THEN** 系统展示其模拟表现指标与账号历史基准对比

### Requirement: 复盘与建议沉淀
系统 SHALL 基于资产库数据生成复盘摘要：记录采用、驳回及模拟后续表现，展示哪些结构/角度表现更好，并输出"下一次优化建议"；建议 MUST 标注依据来源（结构模板/表现数据/证据等级），模拟依据 MUST 标注为模拟。

#### Scenario: 生成复盘摘要
- **WHEN** 用户触发"生成复盘"
- **THEN** 系统输出按结构/角度聚合的模拟表现摘要与优化建议，并注明依据与数据真实性

#### Scenario: 采用驳回记录可查
- **WHEN** 用户查看复盘页
- **THEN** 系统展示全部采用/驳回记录及对应原因，供人工复盘
