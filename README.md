# 动态代理池项目

![架构图](docs/architecture.png)

[![Docker Build](https://img.shields.io/badge/docker%20build-passing-brightgreen)]()
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)]()

自动维护的高可用代理池，支持动态爬取/验证/存储/分配代理

## 主要功能

- 🕷️ 多源代理自动爬取（支持6个代理源，包括快代理/西刺/站大爷/Free Proxy List/ProxyScrape/GeoNode）
- ✅ 代理有效性实时验证（支持HTTP/HTTPS/SOCKS协议）
- 📦 Redis持久化存储
- 🚀 RESTful API 接口（支持按协议过滤、批量获取等功能）
- 📊 代理质量智能评分（基于响应时间的评分机制）
- 🔄 自动维护机制（定期验证、自动触发爬虫）
- 🐳 Docker容器化部署

## 快速开始

### 1. 使用Docker部署
```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 2. API接口说明

| 端点                | 方法 | 说明                         | 参数示例                  |
|---------------------|------|----------------------------|--------------------------|
| `/proxy`            | GET  | 获取随机代理                 | `?protocol=https&count=5` |
| `/proxies`          | GET  | 获取所有代理列表             | `?limit=20&offset=0&protocol=http` |
| `/stats`            | GET  | 系统统计信息                 | -                        |
| `/crawl`            | POST | 触发爬虫任务                 | -                        |
| `/validate`         | POST | 触发代理验证                 | -                        |
| `/proxy`            | POST | 添加新代理                   | `?proxy=http://1.2.3.4:8080` |
| `/proxy/{proxy}`    | DELETE | 删除指定代理               | -                        |

### 3. 环境配置

| 环境变量           | 默认值   | 说明                         |
|--------------------|---------|-----------------------------|
| REDIS_HOST         | redis   | Redis服务器地址              |
| REDIS_PORT         | 6379    | Redis端口                   |
| LOG_LEVEL          | INFO    | 日志级别(DEBUG/INFO/WARNING/ERROR) |
| CRAWL_TIMEOUT      | 30      | 爬虫超时时间(秒)             |
| MAX_PROXIES        | 1000    | 最大代理存储数量             |

## 开发指南

```bash
# 安装依赖
pip install -r requirements.txt

# 启动爬虫
python run.py --crawl

# 启动API服务
python run.py

# 验证所有代理
python run.py --validate
```

## 测试

项目提供了测试脚本，用于验证代理池是否符合动态代理的要求：

```bash
# 运行动态代理测试
python tests/run_tests.py --dynamic

# 运行所有测试
python tests/run_tests.py --all
```

动态代理测试会检查以下指标：
- 代理可用性（成功率）
- IP动态变化率
- 响应时间
- 匿名性
- 代理轮换功能

## 项目结构
```
.
├── app
│   ├── api             # API接口
│   ├── crawlers        # 爬虫模块
│   ├── storage         # 存储模块
│   ├── validator       # 代理验证
│   └── core            # 核心配置
├── tests               # 测试脚本
│   ├── test_dynamic_proxy.py  # 动态代理测试
│   └── run_tests.py    # 测试运行器
├── docker-compose.yml
├── requirements.txt
└── run.py             # 主入口
```

## 监控指标
- 代理总数：`redis_storage.count_proxies()`
- 有效代理比例：通过定时验证维护
- 各站点爬取成功率：记录在日志中

![监控面板](docs/metrics.png)

## 开发进度

### 已完成功能
- ✅ 项目基础架构搭建
  - Docker容器化部署配置
  - Redis存储模块
  - RESTful API接口框架
  - 日志系统
- ✅ 代理爬虫模块
  - 通用爬虫基类（BaseCrawler）
  - 自动发现爬虫机制
  - 已实现3个代理源（快代理、西刺、站大爷）
- ✅ 代理验证系统
  - 代理有效性检查
  - 质量评分机制
  - 定时检查机制（间隔600秒）

### 已优化项
- ✅ 爬虫实现优化
  - 修复原有爬虫无法获取代理的问题
    - 快代理：更新解析逻辑，从JavaScript变量中提取代理数据
    - 西刺代理：增强请求头和重定向处理，改进解析逻辑
    - 站大爷代理：实现多种请求方法和URL尝试，增强错误处理
  - 完善错误处理机制
  - 添加更详细的日志记录
- ✅ 系统功能扩展
  - 添加更多代理源（已添加3个新代理源）
    - Free Proxy List (https://free-proxy-list.net/)
    - ProxyScrape (https://proxyscrape.com/)
    - GeoNode (https://geonode.com/)
  - 优化代理评分算法（基于响应时间的评分机制）
  - 实现代理协议分类（HTTP/HTTPS/SOCKS）
  - 扩展API接口，支持更多功能

### 当前系统状态
- 🟢 基础服务运行正常（Redis + API）
- 🟢 API服务响应正常
- 🟢 爬虫模块已修复并优化
- 🟢 代理验证系统已增强
- 🟢 系统参数配置完成（最小代理数：50）

### 待优化项
- ⏳ 前端界面开发
  - 添加Web管理界面
  - 实现代理池可视化监控
- ⏳ 性能优化
  - 优化大规模代理池的性能
  - 实现分布式爬虫和验证

## 最近更新（2025-03-04）
- 修复了所有原有爬虫的问题，现在可以成功获取代理
- 优化了代理验证器，支持多种协议和响应时间评分
- 改进了主程序，添加了定期验证和自动触发爬虫的功能
- 扩展了API接口，添加了更多端点和功能
- 增强了系统的健壮性和错误处理
- 添加了动态代理测试脚本，用于验证代理池的质量和性能
- 更新README文档，反映当前项目状态
