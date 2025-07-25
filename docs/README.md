# vprism 用户文档

欢迎使用 vprism - 下一代个人金融数据平台！

## 📚 文档导航

### 快速开始
- [快速开始指南](quickstart.md) - 5分钟上手vprism
- [安装指南](installation.md) - 详细安装步骤

### API文档
- [库模式API](api/library.md) - Python库使用
- [Web服务API](api/web.md) - RESTful API文档
- [MCP服务API](api/mcp.md) - MCP协议接口

### 部署指南
- [库模式部署](deployment/library.md)
- [Web服务模式](deployment/web.md)
- [MCP模式部署](deployment/mcp.md)
- [容器化部署](deployment/docker.md)

### 高级主题
- [性能优化](advanced/performance.md)
- [数据质量保证](advanced/data-quality.md)
- [故障排除](advanced/troubleshooting.md)

### 参考
- [配置选项](reference/configuration.md)
- [错误代码](reference/error-codes.md)
- [编码规范](reference/coding-standards.md)
- [示例代码](examples/)

## 🚀 快速示例

```python
import vprism

# 获取股票数据
data = vprism.get("AAPL", market="US", timeframe="1d", limit=100)
print(data.head())

# 使用构建器模式
query = vprism.query() \
    .asset("TSLA") \
    .market("US") \
    .timeframe("1h") \
    .limit(50) \
    .build()

data = vprism.execute(query)
```

## 📞 获取帮助

- 📧 [GitHub Issues](https://github.com/your-repo/vprism/issues)
- 💬 [Discord社区](https://discord.gg/vprism)
- 📖 [FAQ](advanced/faq.md)