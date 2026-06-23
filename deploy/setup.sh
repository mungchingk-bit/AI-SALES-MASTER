#!/bin/bash
# AI Sales Master 云服务器一键部署脚本
# 适用于 Ubuntu 22.04 / 20.04
#
# 使用方式：
#   1. 买好云服务器后，SSH 登录
#   2. 上传此脚本或直接运行：
#      curl -sL <raw-url> | bash
#   3. 或者克隆仓库后运行：
#      bash deploy/setup.sh

set -e

echo "=========================================="
echo "  AI Sales Master 云端部署脚本"
echo "=========================================="

# --- 配置区 ---
REPO_URL="https://github.com/mungchingk-bit/AI-SALES-MASTER.git"
INSTALL_DIR="/opt/ai-sales-master"
PYTHON_VERSION="3.11"

# --- 1. 系统更新 & 基础依赖 ---
echo ""
echo "[1/7] 更新系统 & 安装基础依赖..."
sudo apt-get update -y
sudo apt-get install -y \
    software-properties-common \
    curl \
    git \
    build-essential \
    python3-dev \
    python3-venv \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    fonts-wqy-zenhei \
    fonts-noto-cjk

# --- 2. 安装 Python 3.11 ---
echo ""
echo "[2/7] 安装 Python ${PYTHON_VERSION}..."
if command -v python3.11 &> /dev/null; then
    echo "  Python 3.11 已安装，跳过"
else
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt-get update -y
    sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
fi

# --- 3. 克隆项目 ---
echo ""
echo "[3/7] 克隆项目到 ${INSTALL_DIR}..."
if [ -d "${INSTALL_DIR}" ]; then
    echo "  目录已存在，拉取最新代码..."
    cd "${INSTALL_DIR}"
    git pull origin main
else
    sudo git clone "${REPO_URL}" "${INSTALL_DIR}"
    sudo chown -R $(whoami):$(whoami) "${INSTALL_DIR}"
    cd "${INSTALL_DIR}"
fi

# --- 4. 创建虚拟环境 & 安装依赖 ---
echo ""
echo "[4/7] 创建虚拟环境 & 安装依赖..."
python3.11 -m venv "${INSTALL_DIR}/venv"
source "${INSTALL_DIR}/venv/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

# --- 5. 配置 .env ---
echo ""
echo "[5/7] 配置环境变量..."
if [ ! -f "${INSTALL_DIR}/.env" ]; then
    cat > "${INSTALL_DIR}/.env" << 'ENVEOF'
# === LLM 模型选择 ===
LLM_PROVIDER=openai

# === 国内云端模型配置 ===
OPENAI_API_KEY=在这里填入你的API_KEY
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
OPENAI_MODEL=glm-5.1
FAST_MODEL=glm-4-flash
CLOUD_CONNECT_TIMEOUT=10
CLOUD_RESPONSE_TIMEOUT=60
CLOUD_MAX_RETRIES=2

# === Discord 设置 ===
DISCORD_BOT_TOKEN=在这里填入你的BOT_TOKEN
DISCORD_CHANNEL_ID=在这里填入频道ID
ALLOWED_USER_IDS=在这里填入允许的用户ID

# === 脱敏设置 ===
DESENSITIZE_ENABLED=true
DESENSITIZE_PREVIEW=true
ENVEOF
    echo "  已创建 .env 模板，请编辑填入真实密钥："
    echo "  nano ${INSTALL_DIR}/.env"
    echo ""
    echo "  ⚠️  填好后重新运行此脚本，或手动启动服务"
    exit 0
else
    echo "  .env 已存在，跳过"
fi

# --- 6. 创建 systemd 服务 ---
echo ""
echo "[6/7] 创建系统服务（开机自启 + 崩溃自动重启）..."

# Discord Bot 服务
sudo tee /etc/systemd/system/ai-sales-bot.service > /dev/null << 'SERVICEEOF'
[Unit]
Description=AI Sales Master Discord Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ai-sales-master
ExecStart=/opt/ai-sales-master/venv/bin/python discord_bot.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Web App 服务
sudo tee /etc/systemd/system/ai-sales-web.service > /dev/null << 'SERVICEEOF'
[Unit]
Description=AI Sales Master Web App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ai-sales-master
ExecStart=/opt/ai-sales-master/venv/bin/python app.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICEEOF

sudo systemctl daemon-reload
sudo systemctl enable ai-sales-bot ai-sales-web

# --- 7. 启动服务 ---
echo ""
echo "[7/7] 启动服务..."
sudo systemctl start ai-sales-bot
sudo systemctl start ai-sales-web

echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "服务状态："
echo "  sudo systemctl status ai-sales-bot"
echo "  sudo systemctl status ai-sales-web"
echo ""
echo "查看日志："
echo "  sudo journalctl -u ai-sales-bot -f"
echo "  sudo journalctl -u ai-sales-web -f"
echo ""
echo "Web 访问地址："
echo "  http://$(curl -s ifconfig.me):7860"
echo ""
echo "重启服务："
echo "  sudo systemctl restart ai-sales-bot"
echo "  sudo systemctl restart ai-sales-web"
echo ""
echo "更新代码后："
echo "  cd ${INSTALL_DIR} && git pull && sudo systemctl restart ai-sales-bot ai-sales-web"
