# 人工审核点说明

任何内容**都不能自动发布**。系统只提供候选与辅助，最终决定权在人工。

## 审核状态机

```
Draft → Pending Review → Approved  （进入资产库）
                     → Rejected   （填原因，记录）
                     → Needs Revision（填修改意见，记录）
```

## 人工审核动作

| 动作 | 前置条件 | 结果 |
|---|---|---|
| 提交审核 | 风险等级 LOW 或修改后的 MEDIUM | Draft → Pending Review |
| Approve | 人工点击，风险非 HIGH | Approved，进入资产库 |
| Reject | 人工点击 + 填原因 | Rejected，记录原因 |
| Needs Revision | 人工点击 + 填意见 | Needs Revision，记录意见 |

## 风险等级与审核关系

| 等级 | 含义 | 审核行为 |
|---|---|---|
| LOW | 可进入审核 | 允许人工审核，**不自动批准** |
| MEDIUM | 需修改 | 必须修改后重新检测方可审核 |
| HIGH | Blocked | 禁止进入 Approved 与资产库 |

## 记录内容

每次审核记录：审核动作、审核时间、采用或驳回、驳回原因、修改意见（`review_log` 表）。

## 明确不做

- 不接真实 X 发布（只展示发布预览 + 人工确认）
- 不自动点赞/评论/回复/转帖
- 不购买 X API、不登录用户账号
- 不自动批准任何内容
