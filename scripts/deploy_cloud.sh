#!/usr/bin/env bash
# =============================================================================
# FinSignal Content Agent - one-shot cloud deploy script
# Target: 腾讯云 Lighthouse / 阿里云轻量应用服务器 (Ubuntu 22.04 LTS)
#
# Usage:
#   sudo bash deploy_cloud.sh
#   (or:  bash deploy_cloud.sh   on a root user)
#
# What it does:
#   1. installs Python 3 venv / pip / git
#   2. clones the public GitHub repo
#   3. creates a virtualenv and installs requirements.txt
#   4. registers two systemd services:
#        finsignal-agent1  -> :8501  (Agent 1 · 每日热点 → 候选内容池)
#        finsignal-agent2  -> :8502  (Agent 2 · 爆款拆解 → 二次创作)
#   5. prints the public access URLs
#
# NOTE: remember to open TCP 8501 and 8502 in the cloud security group!
# =============================================================================
set -euo pipefail

REPO_URL="https://github.com/doikind/FOR-TEST.git"
APP_DIR="${APP_DIR:-/opt/finsignal-content-agent}"
AGENT1_PORT="${AGENT1_PORT:-8501}"
AGENT2_PORT="${AGENT2_PORT:-8502}"

echo "==> [1/5] Installing system packages (python3, venv, git)"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git

echo "==> [2/5] Cloning FinSignal Content Agent from GitHub"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

echo "==> [3/5] Creating virtualenv and installing Python dependencies"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo "==> [4/5] Registering systemd services (Agent1:$AGENT1_PORT / Agent2:$AGENT2_PORT)"
cat > /etc/systemd/system/finsignal-agent1.service <<EOF
[Unit]
Description=FinSignal Agent 1 - Hot Topics to Content Pool
After=network.target

[Service]
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/streamlit run app_agent1.py --server.port $AGENT1_PORT --server.address 0.0.0.0
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/finsignal-agent2.service <<EOF
[Unit]
Description=FinSignal Agent 2 - Viral Breakdown to Re-creation
After=network.target

[Service]
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/streamlit run app_agent2.py --server.port $AGENT2_PORT --server.address 0.0.0.0
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable finsignal-agent1 finsignal-agent2
systemctl restart finsignal-agent1 finsignal-agent2

echo "==> [5/5] Deployment finished. Waiting for services to come up..."
sleep 8

systemctl --no-pager --lines=5 status finsignal-agent1 || true
systemctl --no-pager --lines=5 status finsignal-agent2 || true

PUBLIC_IP=$(curl -s --max-time 5 https://api.ipify.org || echo "<your-public-ip>")
echo ""
echo "============================================================================"
echo "  FinSignal Content Agent deployed!"
echo "  Agent 1 (每日热点 → 候选内容池):  http://${PUBLIC_IP}:${AGENT1_PORT}"
echo "  Agent 2 (爆款拆解 → 二次创作):    http://${PUBLIC_IP}:${AGENT2_PORT}"
echo ""
echo "  IMPORTANT: 打开云控制台 → 安全组/防火墙 → 放行 TCP ${AGENT1_PORT} 和 ${AGENT2_PORT}"
echo "============================================================================"
