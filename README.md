# 动态代理池项目

![架构图](docs/architecture.png)

[![Docker Build](https://img.shields.io/badge/docker%20build-passing-brightgreen)]()
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)]()

自动维护的高可用代理池，支持动态爬取/验证/存储/分配代理

## 主要功能

- 🕷️ 多源代理自动爬取（支持快代理/西刺/站大爷等平台）
- ✅ 代理有效性实时验证
- 📦 Redis持久化存储
- 🚀 RESTful API 接口
- 📊 代理质量智能评分
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
| `/proxy`            | GET  | 获取随机代理                 | -                        |
| `/stats`            | GET  | 系统统计信息                 | -                        |

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
```

## 项目结构
```
.
├── app
│   ├── api             # API接口
│   ├── crawlers        # 爬虫模块
│   ├── storage         # 存储模块
│   ├── validator       # 代理验证
│   └── core            # 核心配置
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

### 待优化项
- ⏳ 爬虫实现优化
  - 修复爬虫无法获取代理的问题
    - 快代理：请求成功但未获取到代理，可能网站结构已变化
    - 西刺代理：请求被重定向(302)，需要处理重定向或添加更多请求头
    - 站大爷代理：请求被拒绝(405)，可能需要特定的请求方式或头信息
  - 完善错误处理机制
  - 考虑使用Selenium等工具处理JavaScript渲染的内容
- ⏳ 系统功能扩展
  - 添加更多代理源，减少对单一来源的依赖
  - 优化代理评分算法
  - 实现代理标签分类

### 当前系统状态
- 🟢 基础服务运行正常（Redis + API）
- 🟢 API服务响应正常
- 🔴 代理池为空（爬虫无法获取代理）
- 🟡 系统参数配置完成（最小代理数：50）

## 最近更新（2025-03-04）
- 完成Docker容器化部署
- 验证系统基础功能正常运行
- 发现并记录爬虫模块存在的问题
- 更新README文档，反映当前项目状态
