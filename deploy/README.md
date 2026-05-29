# AI Sales Master 云部署指南

## 一、购买云服务器

推荐配置：
- **腾讯云轻量应用服务器**：2核2G，约 50元/月
- **阿里云 ECS**：2核2G，约 40-60元/月
- 系统：**Ubuntu 22.04**

购买时开放端口：22（SSH）、7860（Web界面）

## 二、SSH 登录服务器

```bash
ssh root@你的服务器IP
```

## 三、一键部署

```bash
# 方式1：直接克隆仓库后运行
git clone https://github.com/mungchingk-bit/AI-SALES-MASTER.git
cd AI-SALES-MASTER
bash deploy/setup.sh
```

首次运行会创建 `.env` 模板，需要编辑填入真实密钥：

```bash
nano /opt/ai-sales-master/.env
```

填好后再次运行：

```bash
bash deploy/setup.sh
```

## 四、手动部署（如需精细控制）

### 1. 安装依赖

```bash
apt update && apt install -y python3.11 python3.11-venv python3.11-dev git tesseract-ocr tesseract-ocr-chi-sim fonts-wqy-zenhei
```

### 2. 克隆项目

```bash
git clone https://github.com/mungchingk-bit/AI-SALES-MASTER.git /opt/ai-sales-master
cd /opt/ai-sales-master
```

### 3. 虚拟环境 & 依赖

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. 配置 .env

```bash
cp .env.example .env
nano .env
```

### 5. 启动服务

```bash
# Discord Bot
nohup python discord_bot.py > bot.log 2>&1 &

# Web App
nohup python app.py > web.log 2>&1 &
```

## 五、日常管理

```bash
# 查看服务状态
sudo systemctl status ai-sales-bot
sudo systemctl status ai-sales-web

# 查看实时日志
sudo journalctl -u ai-sales-bot -f
sudo journalctl -u ai-sales-web -f

# 重启服务
sudo systemctl restart ai-sales-bot ai-sales-web

# 更新代码
cd /opt/ai-sales-master
git pull origin main
pip install -r requirements.txt
sudo systemctl restart ai-sales-bot ai-sales-web
```

## 六、Web 访问

浏览器打开：`http://服务器IP:7860`

如需域名访问，可配置 Nginx 反向代理 + HTTPS。

## 七、注意事项

- `.env` 含 API 密钥，不要泄露
- `data/` 目录存储训练数据，如需迁移可从本地复制
- 服务器防火墙需放行 7860 端口（Web）和 443（Discord Bot 出站）
- 建议定期备份数据：`tar czf backup.tar.gz /opt/ai-sales-master/data/`
