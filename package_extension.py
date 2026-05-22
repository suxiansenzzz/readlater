#!/usr/bin/env python3
"""ReadLater 浏览器扩展打包脚本"""

import os
import zipfile
from pathlib import Path

def package_extension():
    script_dir = Path(__file__).parent
    extension_dir = script_dir / 'extension'
    dist_dir = script_dir / 'dist'
    
    # 创建输出目录
    dist_dir.mkdir(exist_ok=True)
    
    # 打包为 zip 文件
    zip_path = dist_dir / 'readlater-extension.zip'
    
    print('📦 打包 ReadLater 浏览器扩展...')
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(extension_dir):
            # 排除不必要的目录
            dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', '.DS_Store']]
            
            for file in files:
                if file.startswith('.'):
                    continue
                    
                file_path = Path(root) / file
                arc_name = file_path.relative_to(extension_dir)
                zf.write(file_path, arc_name)
    
    print('✅ 打包完成！')
    print()
    print(f'📁 输出文件: {zip_path}')
    print()
    print('📖 安装方法：')
    print()
    print('  Chrome/Edge:')
    print('    1. 打开 chrome://extensions/ 或 edge://extensions/')
    print('    2. 开启「开发者模式」')
    print('    3. 将 zip 文件拖入页面')
    print('    4. 或点击「加载已解压的扩展程序」选择 extension 目录')
    print()
    print('  Firefox:')
    print('    1. 打开 about:debugging#/runtime/this-firefox')
    print('    2. 点击「临时加载附加组件」')
    print('    3. 选择 extension 目录中的 manifest.json')

if __name__ == '__main__':
    package_extension()