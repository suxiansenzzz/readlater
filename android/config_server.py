#!/usr/bin/env python3
"""
快速配置服务器地址脚本
用于修改 APP 连接的服务器地址
"""

import os
import re
import sys

def main():
    print("=" * 50)
    print("ReadLater Android APP 服务器配置")
    print("=" * 50)
    
    # 检查文件
    main_activity = "app/src/main/java/com/readlater/app/MainActivity.java"
    if not os.path.exists(main_activity):
        print("❌ 错误: 找不到 MainActivity.java")
        print(f"   当前目录: {os.getcwd()}")
        print("   请在 android 目录下运行此脚本")
        sys.exit(1)
    
    # 读取当前配置
    with open(main_activity, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 提取当前服务器地址
    match = re.search(r'private static final String SERVER_URL = "(.*?)"', content)
    if match:
        current_url = match.group(1)
        print(f"\n📍 当前服务器地址: {current_url}")
    else:
        print("\n⚠️  未找到服务器地址配置")
        current_url = "http://192.168.31.5:8000"
    
    # 获取新地址
    print("\n请输入新的服务器地址:")
    print("(直接回车保持不变)")
    print()
    
    new_url = input("服务器地址: ").strip()
    
    if not new_url:
        print("\n✅ 保持不变: " + current_url)
        return
    
    # 验证URL格式
    if not new_url.startswith(('http://', 'https://')):
        new_url = 'http://' + new_url
    
    # 移除末尾的斜杠
    new_url = new_url.rstrip('/')
    
    # 更新配置
    new_content = re.sub(
        r'private static final String SERVER_URL = ".*?"',
        f'private static final String SERVER_URL = "{new_url}"',
        content
    )
    
    with open(main_activity, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"\n✅ 服务器地址已更新: {new_url}")
    
    # 更新网络安全配置
    network_config = "app/src/main/res/xml/network_security_config.xml"
    if os.path.exists(network_config):
        from urllib.parse import urlparse
        parsed = urlparse(new_url)
        domain = parsed.hostname
        
        if domain and not domain.startswith('192.168.31.5'):
            with open(network_config, 'r', encoding='utf-8') as f:
                config = f.read()
            
            if domain not in config:
                # 添加新域名
                new_domain = f'        <domain includeSubdomains="true">{domain}</domain>\n'
                config = config.replace(
                    '        <domain includeSubdomains="true">192.168.31.5</domain>',
                    f'        <domain includeSubdomains="true">192.168.31.5</domain>\n{new_domain}'
                )
                
                with open(network_config, 'w', encoding='utf-8') as f:
                    f.write(config)
                
                print(f"✅ 已添加域名到网络安全配置: {domain}")
    
    print("\n" + "=" * 50)
    print("配置完成！")
    print("=" * 50)
    print("\n下一步:")
    print("1. 重新构建 APP: python3 build.py")
    print("2. 安装新 APK 到手机")
    print()

if __name__ == "__main__":
    main()
