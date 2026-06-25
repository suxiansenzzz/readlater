#!/usr/bin/env python3
"""
ReadLater Android APP 构建脚本
自动配置服务器地址并构建APK
"""

import os
import sys
import subprocess
import shutil

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_colored(text, color):
    print(f"{color}{text}{Colors.END}")

def print_header(text):
    print_colored(f"\n{'='*50}", Colors.HEADER)
    print_colored(text, Colors.HEADER + Colors.BOLD)
    print_colored(f"{'='*50}", Colors.HEADER)

def print_success(text):
    print_colored(f"✅ {text}", Colors.GREEN)

def print_error(text):
    print_colored(f"❌ {text}", Colors.RED)

def print_info(text):
    print_colored(f"ℹ️  {text}", Colors.BLUE)

def print_warning(text):
    print_colored(f"⚠️  {text}", Colors.YELLOW)

def check_requirements():
    """检查构建环境"""
    print_header("检查构建环境")
    
    # 检查Java
    try:
        result = subprocess.run(['java', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            print_success("Java 已安装")
        else:
            print_error("Java 未安装")
            return False
    except FileNotFoundError:
        print_error("Java 未安装")
        print_info("请安装 Java JDK 8 或更高版本")
        print_info("Ubuntu/Debian: sudo apt install openjdk-17-jdk")
        print_info("macOS: brew install openjdk@17")
        return False
    
    # 检查Android SDK（可选）
    android_home = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if android_home:
        print_success(f"Android SDK: {android_home}")
    else:
        print_warning("Android SDK 未配置")
        print_info("如果没有Android SDK，可以使用在线构建服务")
    
    return True

def configure_server():
    """配置服务器地址"""
    print_header("配置服务器地址")
    
    print_info("当前默认服务器地址: http://192.168.31.5:8000")
    print_info("如果是局域网部署，保持默认即可")
    print_info("如果是公网部署，请输入公网地址")
    
    server_url = input("\n请输入服务器地址 (直接回车使用默认): ").strip()
    
    if not server_url:
        server_url = "http://192.168.31.5:8000"
    
    # 验证URL格式
    if not server_url.startswith(('http://', 'https://')):
        server_url = 'http://' + server_url
    
    # 移除末尾的斜杠
    server_url = server_url.rstrip('/')
    
    print_success(f"服务器地址: {server_url}")
    
    # 更新MainActivity.java
    main_activity_path = "app/src/main/java/com/readlater/app/MainActivity.java"
    if os.path.exists(main_activity_path):
        with open(main_activity_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换服务器地址
        import re
        content = re.sub(
            r'private static final String SERVER_URL = ".*?";',
            f'private static final String SERVER_URL = "{server_url}";',
            content
        )
        
        with open(main_activity_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print_success("服务器地址已更新")
    
    return server_url

def update_network_config(server_url):
    """更新网络安全配置"""
    print_info("更新网络安全配置...")
    
    network_config_path = "app/src/main/res/xml/network_security_config.xml"
    
    # 提取域名
    from urllib.parse import urlparse
    parsed = urlparse(server_url)
    domain = parsed.hostname
    
    # 如果是IP地址或localhost，添加到配置
    if domain and (domain.startswith('192.168.') or domain.startswith('10.') or 
                   domain == 'localhost' or domain == '127.0.0.1'):
        with open(network_config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查域名是否已存在
        if domain not in content:
            # 添加新域名
            new_domain = f'        <domain includeSubdomains="true">{domain}</domain>\n'
            content = content.replace(
                '        <domain includeSubdomains="true">192.168.31.5</domain>',
                f'        <domain includeSubdomains="true">192.168.31.5</domain>\n{new_domain}'
            )
            
            with open(network_config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print_success(f"已添加域名 {domain} 到网络安全配置")

def build_apk():
    """构建APK"""
    print_header("构建 APK")
    
    if not os.path.exists('gradlew'):
        print_error("gradlew 文件不存在")
        print_info("请确保在 android 目录下运行此脚本")
        return False
    
    # 给gradlew执行权限
    os.chmod('gradlew', 0o755)
    
    print_info("正在构建 Release APK...")
    print_info("首次构建可能需要下载依赖，请耐心等待...")
    
    try:
        # 清理并构建
        result = subprocess.run(
            ['./gradlew', 'assembleRelease', '--no-daemon'],
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )
        
        if result.returncode == 0:
            print_success("构建成功！")
            
            # 查找APK文件
            apk_path = None
            for root, dirs, files in os.walk('app/build/outputs/apk'):
                for file in files:
                    if file.endswith('.apk'):
                        apk_path = os.path.join(root, file)
                        break
                if apk_path:
                    break
            
            if apk_path:
                # 复制到项目根目录
                dest_path = 'readlater.apk'
                shutil.copy2(apk_path, dest_path)
                print_success(f"APK 已生成: {os.path.abspath(dest_path)}")
                return True
            else:
                print_error("未找到生成的APK文件")
                return False
        else:
            print_error("构建失败")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print_error("构建超时")
        return False
    except Exception as e:
        print_error(f"构建出错: {e}")
        return False

def show_manual_build_info():
    """显示手动构建说明"""
    print_header("手动构建说明")
    
    print_info("""
如果没有 Android SDK，可以使用以下方法：

方法1: 使用 GitHub Actions 自动构建
1. 将 android 目录上传到 GitHub 仓库
2. 创建 .github/workflows/build.yml 文件
3. 推送代码后会自动构建 APK

方法2: 使用 Android Studio
1. 下载安装 Android Studio
2. 打开 android 目录
3. 等待 Gradle 同步完成
4. 菜单 Build -> Build Bundle(s) / APK(s) -> Build APK(s)

方法3: 使用在线构建服务
- https://build.phonegap.com/
- https://www.appgyver.com/
""")

def show_usage_info():
    """显示使用说明"""
    print_header("使用说明")
    
    print_info("""
📱 安装 APP:
1. 将 readlater.apk 传输到手机
2. 打开文件管理器，点击 APK 文件安装
3. 如果提示"未知来源"，需要在设置中允许

⚙️ 配置服务器:
APP 默认连接 http://192.168.31.5:8000
如果服务器地址变化，需要重新构建 APP

🔧 兼容性:
- 最低支持: Android 7.0 (API 24)
- 目标版本: Android 14 (API 34)
- 支持架构: ARM, ARM64, x86, x86_64
- 小米澎湃OS: 完全兼容
- 其他安卓: 兼容

💡 提示:
- 首次打开可能需要等待加载
- 确保手机和服务器在同一网络
- 如果无法连接，检查服务器地址配置
""")

def main():
    """主函数"""
    print_header("ReadLater Android APP 构建工具")
    print_info("版本: 1.0.0")
    print_info("支持: 小米澎湃OS4 + 全安卓兼容")
    
    # 检查当前目录
    if not os.path.exists('app'):
        print_error("请在 android 目录下运行此脚本")
        print_info(f"当前目录: {os.getcwd()}")
        sys.exit(1)
    
    # 配置服务器
    server_url = configure_server()
    
    # 更新网络配置
    update_network_config(server_url)
    
    # 检查环境
    if check_requirements():
        # 构建APK
        if build_apk():
            show_usage_info()
        else:
            print_error("构建失败，请查看上方错误信息")
            show_manual_build_info()
    else:
        show_manual_build_info()
    
    print_header("完成")

if __name__ == "__main__":
    main()
