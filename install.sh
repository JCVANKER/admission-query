# ── 系统依赖安装（Ubuntu/Debian）──
# 先运行：sudo bash install.sh

# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 和必要工具
sudo apt install -y python3 python3-pip python3-venv nginx git

# 安装 pip 依赖
pip3 install flask gunicorn --break-system-packages
