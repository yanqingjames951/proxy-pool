#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
代理池测试运行脚本

该脚本用于运行各种测试，检查代理池是否符合要求
"""

import os
import sys
import argparse
import asyncio
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入测试模块
from tests.test_dynamic_proxy import main as test_dynamic_proxy

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="代理池测试工具")
    parser.add_argument("--dynamic", action="store_true", help="运行动态代理测试")
    parser.add_argument("--all", action="store_true", help="运行所有测试")
    return parser.parse_args()

async def run_tests(args):
    """运行测试"""
    results = {}
    
    if args.dynamic or args.all:
        logger.info("开始运行动态代理测试...")
        dynamic_result = await test_dynamic_proxy()
        results["动态代理测试"] = "通过" if dynamic_result else "未通过"
    
    # 打印测试结果摘要
    if results:
        print("\n" + "="*50)
        print("测试结果摘要")
        print("="*50)
        for test_name, result in results.items():
            status = "✅" if result == "通过" else "❌"
            print(f"{status} {test_name}: {result}")
        print("="*50)
    else:
        print("\n未运行任何测试。使用 --dynamic 或 --all 参数来运行测试。")
        print("例如: python run_tests.py --dynamic")

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_tests(args))
