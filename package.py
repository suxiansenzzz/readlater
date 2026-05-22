#!/usr/bin/env python3
"""ReadLater 完整项目打包脚本"""

import os
import zipfile
import shutil
from pathlib import Path
from datetime import datetime

def create_package():
    script_dir = Path(__file__).parent
    dist_dir = script_dir / 'dist'
    
    # 清理并创建输出目录
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir()
    
    # 打包文件名（带日期）
    date_str = datetime.now().strftime('%Y%m%d')
    zip_name = f'ReadLater-{date_str}.zip'
    zip_path = dist_dir / zip_name
    
    print('📦 打包 ReadLater 完整项目...')
    print()
    
    # 需要打包的文件和目录
    include_items = [
        # 后端代码
        ('backend/main_v2.py', 'backend/main.py'),
        ('backend/main_v3.py', 'backend/main_v3.py'),
        
        # 前端代码
        ('static/index.html', 'static/index.html'),
        ('static/index_v3.html', 'static/index_v3.html'),
        
        # 浏览器扩展
        'extension/',
        
        # Docker 部署文件
        ('Dockerfile', 'Dockerfile'),
        ('docker-compose.yml', 'docker-compose.yml'),
        ('.dockerignore', '.dockerignore'),
        
        # 启动脚本
        'build.sh',
        'start.sh',
        'stop.sh',
        'package_extension.py',
        
        # 依赖文件
        'requirements.txt',
        
        # 文档
        'README.md',
        'SETUP.md',
        'DOCKER.md',
    ]
    
    # 排除的目录
    exclude_dirs = {
        '__pycache__',
        '.git',
        '.github',
        'node_modules',
        'venv',
        '.venv',
        'dist',
        'ugapp',
    }
    
    # 排除的文件
    exclude_files = {
        '.DS_Store',
        'Thumbs.db',
        '*.pyc',
        '*.pyo',
        '*.db',
    }
    
    def should_exclude(path: Path) -> bool:
        """检查是否应该排除"""
        for part in path.parts:
            if part in exclude_dirs:
                return True
        if path.name in exclude_files:
            return True
        if path.name.endswith('.pyc') or path.name.endswith('.pyo'):
            return True
        return False
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 添加特定文件
        for item in include_items:
            if isinstance(item, tuple):
                src, dst = item
                src_path = script_dir / src
                if src_path.exists():
                    zf.write(src_path, f'ReadLater/{dst}')
                    print(f'  ✅ {src}')
            else:
                item_path = script_dir / item
                if item_path.is_file():
                    zf.write(item_path, f'ReadLater/{item}')
                    print(f'  ✅ {item}')
                elif item_path.is_dir():
                    for root, dirs, files in os.walk(item_path):
                        # 排除目录
                        dirs[:] = [d for d in dirs if d not in exclude_dirs]
                        
                        for file in files:
                            file_path = Path(root) / file
                            if should_exclude(file_path):
                                continue
                            
                            arc_name = file_path.relative_to(script_dir)
                            zf.write(file_path, f'ReadLater/{arc_name}')
                    print(f'  ✅ {item}/')
    
    # 计算文件大小
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    
    print()
    print('=' * 50)
    print('✅ 打包完成！')
    print()
    print(f'📁 文件：{zip_path}')
    print(f'📊 大小：{size_mb:.2f} MB')
    print()
    print('📦 包含内容：')
    print('  - 后端服务（Python FastAPI）')
    print('  - 前端界面（HTML/CSS/JS）')
    print('  - 浏览器扩展（Chrome/Edge）')
    print('  - Docker 部署文件')
    print('  - 完整文档')
    print()
    print('🚀 快速开始：')
    print('  1. 解压文件')
    print('  2. 服务器部署：./start.sh')
    print('  3. 安装扩展：参考 SETUP.md')
    print('=' * 50)
    
    return zip_path

if __name__ == '__main__':
    create_package()