# GitHub 提交前安全检查

提交前逐项确认：

## 敏感信息

- [ ] `.env` 未提交（已加入 `.gitignore`）
- [ ] `.env.example` 中无真实密钥（全部留空）
- [ ] `finsignal.db` 未提交（运行时生成，已 gitignore）
- [ ] 无硬编码 API Key / token / 密码

## 数据合规

- [ ] `data/snapshots/` 快照为**真实公开数据**，无隐私、无版权敏感内容
- [ ] `data/simulated/` 模拟数据已明确标注 `simulated_demo`，不冒充真实
- [ ] 未保存完整 X 帖子，仅 Post ID / 来源 URL / 必要片段 / 派生特征
- [ ] 未声称拥有竞品点击率等非公开指标

## 内容合规

- [ ] 免责声明 "informational purposes only, not investment advice" 在 UI 常显
- [ ] 无"保证收益""确定性价格预测""直接荐股"类内容
- [ ] 无敏感地区问题表述

## 代码卫生

- [ ] `.py-deps/`、`.venv/`、`.dsh-tmp/`、`__pycache__/` 未提交（已 gitignore）
- [ ] 无调试 print/临时文件
- [ ] 依赖在 `requirements.txt` 中完整声明

## 一键检查命令

```powershell
git status --short
git check-ignore -v .env finsignal.db .py-deps .venv  # 应显示被忽略
```

## 建议提交清单

```
README.md  app.py  cli.py  core/  agents/  ui/  data/  docs/  scripts/
requirements.txt  .env.example  .gitignore
```
