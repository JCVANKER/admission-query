# ── 一键部署脚本 ──
# 使用方法: sudo bash deploy.sh

set -e

echo "===== 1. 安装系统依赖 ====="
apt update
apt install -y python3 python3-pip python3-venv nginx supervisor

echo "===== 2. 安装 Python 依赖 ====="
pip3 install flask gunicorn --break-system-packages

echo "===== 3. 部署项目文件 ====="
mkdir -p /opt/admission-query
cp -r . /opt/admission-query/
rm -rf /opt/admission-query/.git /opt/admission-query/__pycache__

echo "===== 4. 配置 Nginx ====="
cp nginx.conf /etc/nginx/sites-available/admission-query
ln -sf /etc/nginx/sites-available/admission-query /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo "===== 5. 配置 Supervisor ====="
cp supervisor.conf /etc/supervisor/conf.d/admission-query.conf
supervisorctl reread
supervisorctl update
supervisorctl start admission-query

echo "===== 6. 初始化数据库 ====="
cd /opt/admission-query
python3 -c "from app import init_db; init_db()"
chown -R www-data:www-data /opt/admission-query

echo ""
echo "✅ 部署完成！"
echo "访问 http://服务器IP 即可使用"
echo ""
echo "⚠️ 请立即做以下安全设置："
echo "1. 修改 /opt/admission-query/.env 中的密码"
echo "2. 修改 /etc/supervisor/conf.d/admission-query.conf 中的环境变量"
echo "3. 配置 SSL 证书（推荐使用 Let's Encrypt）"
