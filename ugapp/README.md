# ReadLater 绿联NAS应用包

## 项目结构

```
ugapp/
├── project.yaml          # 应用配置文件
├── requirements.txt      # Python依赖
├── rootfs_common/        # 通用文件
│   ├── backend/
│   │   ├── main.py       # 后端主程序
│   │   └── readlater.db  # 数据库模板
│   ├── www/
│   │   └── static/
│   │       └── index.html # 前端页面
│   ├── icon.svg          # 应用图标
│   └── postinst.sh       # 安装后脚本
└── rootfs_amd64/         # amd64架构文件
    └── bin/
        └── readlater     # 启动脚本
```

## 打包步骤

1. 安装ugcli工具（从绿联云开发者平台下载）
2. 准备绿联NAS设备并获取开发者授权
3. 在ugapp目录下运行打包命令：
   ```bash
   ugcli pack
   ```
4. 生成的.upk文件可以在绿联NAS上安装测试

## 功能特性

- 网页内容抓取和保存
- 文章阅读和管理
- 标签分类
- 已读/未读状态
- 收藏功能
- 搜索和筛选
- 统计信息

## 开发说明

- 后端：Python + FastAPI
- 前端：原生HTML/CSS/JavaScript
- 数据库：SQLite
- 支持架构：amd64, arm64