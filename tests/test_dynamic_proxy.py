#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
动态代理测试脚本

该脚本用于测试代理池是否符合动态代理的要求，包括：
1. IP动态变化
2. 代理可用性
3. 匿名性
4. 响应速度
5. 自动更新机制
"""

import sys
import os
import time
import json
import asyncio
import aiohttp
import requests
from urllib.parse import urlparse
import logging
from concurrent.futures import ThreadPoolExecutor
import random

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入项目模块
from app.storage.redis_client import redis_storage
from app.validator.proxy_validator import ProxyValidator

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 测试配置
TEST_CONFIG = {
    'test_url': 'https://httpbin.org/ip',        # 用于获取IP的测试URL
    'test_count': 10,                            # 测试次数
    'timeout': 10,                               # 请求超时时间（秒）
    'max_proxies': 20,                           # 最大测试代理数量
    'protocols': ['http', 'https'],              # 要测试的协议
    'api_url': 'http://localhost:8000/proxy',    # 代理池API地址
    'use_api': True,                             # 是否使用API获取代理
}

class DynamicProxyTester:
    """动态代理测试器"""
    
    def __init__(self, config=None):
        self.config = config or TEST_CONFIG
        self.validator = ProxyValidator()
        self.results = {
            'total_tested': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'unique_ips': set(),
            'response_times': [],
            'details': []
        }
    
    async def get_proxies_from_redis(self):
        """从Redis代理池获取代理"""
        all_proxies = await redis_storage.get_proxies(100)
        
        # 按协议过滤代理
        filtered_proxies = []
        for proxy in all_proxies:
            protocol = proxy.split('://')[0] if '://' in proxy else 'unknown'
            if protocol in self.config['protocols']:
                filtered_proxies.append(proxy)
        
        # 限制测试代理数量
        return filtered_proxies[:self.config['max_proxies']]
    
    def get_proxies_from_api(self):
        """从API获取代理"""
        proxies = []
        try:
            for _ in range(self.config['max_proxies']):
                response = requests.get(self.config['api_url'], timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    proxy = data.get('proxy')
                    if proxy:
                        proxies.append(proxy)
                time.sleep(0.5)  # 避免请求过于频繁
        except Exception as e:
            logger.error(f"从API获取代理失败: {str(e)}")
        
        return proxies
    
    async def test_proxy(self, proxy):
        """测试单个代理"""
        protocol = proxy.split('://')[0] if '://' in proxy else 'http'
        proxy_url = proxy if '://' in proxy else f"http://{proxy}"
        
        result = {
            'proxy': proxy,
            'protocol': protocol,
            'success': False,
            'ip': None,
            'response_time': None,
            'error': None,
            'anonymous': False
        }
        
        try:
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.config['test_url'],
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=self.config['timeout']),
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        result['success'] = True
                        result['ip'] = data.get('origin', '').split(',')[0].strip()
                        result['response_time'] = round((time.time() - start_time) * 1000, 2)  # 毫秒
                        
                        # 检查匿名性
                        headers_response = await session.get(
                            'https://httpbin.org/headers',
                            proxy=proxy_url,
                            timeout=aiohttp.ClientTimeout(total=self.config['timeout']),
                            headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                            }
                        )
                        if headers_response.status == 200:
                            headers_data = await headers_response.json()
                            # 检查是否暴露原始IP
                            result['anonymous'] = 'X-Forwarded-For' not in headers_data.get('headers', {})
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    async def run_dynamic_test(self):
        """运行动态代理测试"""
        logger.info("开始动态代理测试...")
        
        # 获取代理
        if self.config['use_api']:
            proxies = self.get_proxies_from_api()
            logger.info(f"从API获取了 {len(proxies)} 个代理")
        else:
            proxies = await self.get_proxies_from_redis()
            logger.info(f"从Redis获取了 {len(proxies)} 个代理")
        
        if not proxies:
            logger.error("没有获取到代理，测试终止")
            return self.results
        
        # 运行测试
        for i in range(self.config['test_count']):
            logger.info(f"测试轮次 {i+1}/{self.config['test_count']}")
            
            # 随机选择一个代理
            proxy = random.choice(proxies)
            
            # 测试代理
            result = await self.test_proxy(proxy)
            self.results['total_tested'] += 1
            
            if result['success']:
                self.results['successful_requests'] += 1
                self.results['unique_ips'].add(result['ip'])
                self.results['response_times'].append(result['response_time'])
            else:
                self.results['failed_requests'] += 1
            
            self.results['details'].append(result)
            
            # 等待一小段时间
            await asyncio.sleep(1)
        
        # 计算结果统计
        self.calculate_statistics()
        
        return self.results
    
    def calculate_statistics(self):
        """计算测试统计信息"""
        # 计算成功率
        if self.results['total_tested'] > 0:
            self.results['success_rate'] = round(self.results['successful_requests'] / self.results['total_tested'] * 100, 2)
        else:
            self.results['success_rate'] = 0
        
        # 计算IP变化率
        if self.results['successful_requests'] > 0:
            self.results['ip_change_rate'] = round(len(self.results['unique_ips']) / self.results['successful_requests'] * 100, 2)
        else:
            self.results['ip_change_rate'] = 0
        
        # 计算平均响应时间
        if self.results['response_times']:
            self.results['avg_response_time'] = round(sum(self.results['response_times']) / len(self.results['response_times']), 2)
        else:
            self.results['avg_response_time'] = 0
        
        # 计算匿名代理比例
        anonymous_count = sum(1 for result in self.results['details'] if result.get('anonymous', False))
        if self.results['successful_requests'] > 0:
            self.results['anonymous_rate'] = round(anonymous_count / self.results['successful_requests'] * 100, 2)
        else:
            self.results['anonymous_rate'] = 0
        
        # 转换unique_ips为列表以便JSON序列化
        self.results['unique_ips'] = list(self.results['unique_ips'])
    
    def print_results(self):
        """打印测试结果"""
        print("\n" + "="*50)
        print("动态代理测试结果")
        print("="*50)
        print(f"总测试次数: {self.results['total_tested']}")
        print(f"成功请求数: {self.results['successful_requests']}")
        print(f"失败请求数: {self.results['failed_requests']}")
        print(f"成功率: {self.results['success_rate']}%")
        print(f"唯一IP数量: {len(self.results['unique_ips'])}")
        print(f"IP变化率: {self.results['ip_change_rate']}%")
        print(f"平均响应时间: {self.results['avg_response_time']}ms")
        print(f"匿名代理比例: {self.results['anonymous_rate']}%")
        print("="*50)
        
        # 打印详细结果
        print("\n详细测试结果:")
        for i, result in enumerate(self.results['details']):
            status = "✅" if result['success'] else "❌"
            ip_info = f"IP: {result['ip']}" if result['ip'] else "IP: N/A"
            time_info = f"响应时间: {result['response_time']}ms" if result['response_time'] else "响应时间: N/A"
            anon_info = "匿名: ✓" if result.get('anonymous', False) else "匿名: ✗"
            error_info = f"错误: {result['error']}" if result['error'] else ""
            
            print(f"{i+1}. {status} 代理: {result['proxy']} | {ip_info} | {time_info} | {anon_info} {error_info}")
    
    def save_results(self, filename="dynamic_proxy_test_results.json"):
        """保存测试结果到文件"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        logger.info(f"测试结果已保存到 {filename}")

async def test_proxy_pool_api():
    """测试代理池API是否正常运行"""
    try:
        response = requests.get('http://localhost:8000/stats', timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"代理池API正常运行，当前代理数量: {data.get('total_proxies', 0)}")
            return True
        else:
            logger.error(f"代理池API返回错误状态码: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"代理池API测试失败: {str(e)}")
        return False

async def test_proxy_rotation():
    """测试代理轮换功能"""
    logger.info("开始测试代理轮换功能...")
    
    ips = set()
    success_count = 0
    
    for i in range(10):
        try:
            response = requests.get('http://localhost:8000/proxy', timeout=5)
            if response.status_code == 200:
                proxy_data = response.json()
                proxy = proxy_data.get('proxy')
                
                if proxy:
                    # 使用获取的代理请求测试URL
                    proxy_url = proxy if '://' in proxy else f"http://{proxy}"
                    ip_response = requests.get(
                        'https://httpbin.org/ip',
                        proxies={'http': proxy_url, 'https': proxy_url},
                        timeout=10
                    )
                    
                    if ip_response.status_code == 200:
                        ip_data = ip_response.json()
                        ip = ip_data.get('origin', '').split(',')[0].strip()
                        ips.add(ip)
                        success_count += 1
                        logger.info(f"轮换测试 {i+1}/10: 成功 | 代理: {proxy} | IP: {ip}")
                    else:
                        logger.warning(f"轮换测试 {i+1}/10: IP请求失败 | 代理: {proxy}")
                else:
                    logger.warning(f"轮换测试 {i+1}/10: 未获取到代理")
            else:
                logger.warning(f"轮换测试 {i+1}/10: API返回错误状态码: {response.status_code}")
        except Exception as e:
            logger.error(f"轮换测试 {i+1}/10: 出错 - {str(e)}")
        
        # 等待一小段时间
        await asyncio.sleep(1)
    
    # 计算结果
    if success_count > 0:
        unique_rate = len(ips) / success_count * 100
        logger.info(f"代理轮换测试完成: 成功率 {success_count/10*100}%, 唯一IP比例 {unique_rate}%")
        return unique_rate >= 50  # 如果至少50%的请求使用了不同的IP，则认为轮换功能正常
    else:
        logger.error("代理轮换测试失败: 没有成功的请求")
        return False

async def main():
    """主函数"""
    # 测试代理池API
    api_running = await test_proxy_pool_api()
    
    if not api_running:
        logger.warning("代理池API未运行，将使用Redis直接获取代理")
        TEST_CONFIG['use_api'] = False
    
    # 测试代理轮换功能
    if api_running:
        rotation_works = await test_proxy_rotation()
        if rotation_works:
            logger.info("代理轮换功能测试通过")
        else:
            logger.warning("代理轮换功能测试未通过，可能无法提供动态IP")
    
    # 运行动态代理测试
    tester = DynamicProxyTester(TEST_CONFIG)
    results = await tester.run_dynamic_test()
    
    # 打印和保存结果
    tester.print_results()
    tester.save_results()
    
    # 判断是否符合动态代理要求
    meets_requirements = (
        results['success_rate'] >= 70 and  # 成功率至少70%
        results['ip_change_rate'] >= 50 and  # IP变化率至少50%
        results['avg_response_time'] <= 2000  # 平均响应时间不超过2秒
    )
    
    if meets_requirements:
        logger.info("✅ 测试通过！代理池符合动态代理的要求")
        return True
    else:
        logger.warning("❌ 测试未通过！代理池不完全符合动态代理的要求")
        
        # 输出具体不符合的要求
        if results['success_rate'] < 70:
            logger.warning(f"- 成功率过低: {results['success_rate']}% < 70%")
        if results['ip_change_rate'] < 50:
            logger.warning(f"- IP变化率过低: {results['ip_change_rate']}% < 50%")
        if results['avg_response_time'] > 2000:
            logger.warning(f"- 平均响应时间过长: {results['avg_response_time']}ms > 2000ms")
        
        return False

if __name__ == "__main__":
    asyncio.run(main())
