# Hugging Face Spaces 公网部署（推荐）

免费、公网直开、面试官可直接访问，无需本地电脑在线，无需 API token。

## 方式一：从 GitHub 关联部署（推荐，自动同步）

1. 打开 https://huggingface.co/new-space
2. 填写：
   - **Space name**: `finsignal-agent1`
   - **License**: `mit`
   - **SDK**: 选 **Streamlit**
   - 勾选 **"Link to a GitHub repo (Optional)"** → 选 `doikind/FOR-TEST`
3. Create Space，HF 会拉取仓库并自动构建

## 方式二：zip 上传部署（最可控）

1. 在项目根目录打包（排除依赖与数据库）：
   ```powershell
   Compress-Archive -Path core,agents,ui,data,scripts,app.py,requirements.txt,.streamlit -DestinationPath finsignal-hf.zip
   ```
2. 打开 https://huggingface.co/new-space → SDK 选 **Streamlit** → 拖入 zip 上传
3. 构建完成后得到公网 URL：`https://<你的用户名>-finsignal-agent1.hf.space`

## 部署后

- Agent 1 默认入口是 `app.py`（已指向热点→候选池主闭环）
- 若需要 Agent 2，再建一个 Space，SDK=Streamlit，Main file 上传 `app_agent2.py`
- 免费版 Space 闲置会休眠，访问时自动唤醒（首次打开约 30 秒）

## 注意事项

- 云端 Linux 环境会安装 `requirements.txt`（scikit-learn/scipy 构建约 1-2 分钟）
- X 相关数据源在云端可能受限，自动回退仓库快照（`data/snapshots/`）
- 云端 SQLite 为临时存储，仅用于演示；持久化需接外部数据库
