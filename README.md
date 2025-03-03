# 代理池项目

## 项目简介
一个自动化抓取免费代理IP并进行验证的代理池系统，提供动态代理接口服务

## 主要功能
- 多平台代理源抓取
- IP有效性验证
- Redis持久化存储
- RESTful API接口
- Docker容器化部署

## 技术栈
- Python 3.8+
- FastAPI
- Redis
- Docker
- Requests

## 开发进度

### 已完成功能 ✅
1. **核心框架**
   - 基础爬虫抽象类 (base_crawler.py)
   - 代理验证器 (proxy_validator.py)
   - Redis存储客户端 (redis_client.py)

2. **数据源实现**
   - 快代理爬虫 (kuaidaili.py)
   - 西刺代理爬虫 (xicidaili.py)
   - 站大爷爬虫 (zdaye.py)

3. **服务接口**
   - FastAPI路由配置 (router.py)
   - 代理获取接口 `/random`
   - 统计信息接口 `/status`

4. **基础设施**
   - Docker容器化配置
   - 环境配置管理 (config.py)
   - 依赖管理 (requirements.txt)

## 使用指南

```bash
# 启动服务
docker-compose up -d

# 执行爬取任务
docker exec -it proxy-pool python run.py --crawl

# 访问API文档
http://localhost:8000/docs
```

## 后续计划
- [ ] 增加更多代理源
- [ ] 实现代理权重评分机制
- [ ] 添加监控告警功能
- [ ] 完善测试覆盖率
