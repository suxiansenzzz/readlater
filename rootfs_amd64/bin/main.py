#!/usr/bin/env python3
import os
import sys
import subprocess

# 获取应用目录
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMON_DIR = os.path.join(APP_DIR, '..', 'rootfs_common')

# 切换到应用目录
os.chdir(COMMON_DIR)

# 安装依赖
if not os.path.exists('.deps_installed'):
    print("正在安装依赖...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt', '-q'])
    open('.deps_installed', 'w').close()

# 启动应用
print("启动 ReadLater...")
from main import app
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)
