# AI 使用说明

## 原则

AI 生成**与业务逻辑解耦**，封装为独立 provider 接口。系统在**无 API Key** 时完整可用，绝不因缺 Key 而瘫痪，也绝不把缓存/模板输出冒充为实时模型调用。

## Provider 抽象

`agents/ai_provider.py` 定义统一接口，业务层（摘要、角度、候选生成）只依赖接口：

```
get_provider() → CacheProvider( OpenAICompatProvider | TemplateProvider )
```

解析顺序：**缓存 → 实时模型（有 Key）→ 模板降级**。

| Provider | 触发条件 | 输出标注 |
|---|---|---|
| `CacheProvider` | 相同输入命中 `ai_cache` 表 | `AI 输出缓存` |
| `OpenAICompatProvider` | 配置 `OPENAI_API_KEY` | `实时模型` |
| `TemplateProvider` | 无 Key / 调用失败回退 | `模板模式` |

## 缓存机制

- 输入哈希：`hash(title + angles)`
- 命中缓存直接返回，**不重复调用模型**，并在每条候选标注 `AI 输出缓存`
- 缓存**明确标注**，绝不冒充现场实时模型调用

## 无 Key 的 Demo 模式

未配置 `OPENAI_API_KEY` 时：
- 摘要/角度/候选由 `TemplateProvider` 用规则模板生成（标注 `模板模式`）
- 采集、去重、评分、风险检查、审核、存储**全部真实运行**
- 这是默认演示模式

## 配置（可选）

复制 `.env.example` → `.env`：

```
OPENAI_API_KEY=           # 留空 = Demo 模式
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

支持任意 OpenAI 兼容端点（如 DeepSeek），由 `OPENAI_BASE_URL` 决定。

## 约束

- 不训练模型、不称"模型学习"
- 缓存输出不冒充实时调用
- 模型调用失败自动回退模板并提示降级原因
