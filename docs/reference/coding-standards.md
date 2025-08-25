# vprism 编码规范

本文档定义了vprism项目的编码标准和命名约定。

## 命名约定

### 命名规则

- 非代码文本中统一使用小写 `vprism`。
- 类名以 `VPrism` 为前缀并采用 PascalCase。
- 模块、函数与变量使用 `vprism_` 前缀并采用 snake_case。
- 环境变量使用 `VPRISM_` 前缀并采用 SCREAMING_SNAKE_CASE。
- 常量使用 UPPER_SNAKE_CASE。

## 代码组织

### 模块结构
```
src/vprism/
├── core/                    # 核心业务逻辑
│   ├── models.py           # 数据模型
│   └── services/           # 业务服务
├── infrastructure/         # 基础设施层
│   ├── providers/          # 数据提供商适配器
│   ├── repositories/       # 数据仓储
│   └── cache/             # 缓存实现
└── web/                   # Web接口
```

### 提供商命名规范
所有数据提供商适配器应遵循以下规范：

1. **文件命名**: `{provider_name}.py`
   - 例如: `akshare.py`, `yfinance.py`, `alpha_vantage.py`

2. **类命名**: `{ProviderName}`
   - 例如: `class AkShare`, `class YFinance`, `class AlphaVantage`
   - **不包含** `Provider` 后缀

3. **导入方式**:
   ```python
   from vprism.infrastructure.providers.akshare import AkShare
   from vprism.infrastructure.providers.yfinance import YFinance
   ```

### 测试文件命名
- 测试文件以 `test_` 前缀命名
- 测试类以 `Test` 前缀命名
- 测试方法以 `test_` 前缀命名

## 代码风格

### 导入规范
- 标准库导入在前
- 第三方库导入在中
- 本地模块导入在后
- 每组导入按字母顺序排序

### 文档字符串
- 所有公共类和方法必须有文档字符串
- 使用三重双引号格式
- 包含参数说明和返回值说明

### 类型提示
- 所有公共方法和函数必须包含类型提示
- 使用 `from typing import ...` 导入类型
- 复杂类型应使用 `TypeAlias` 定义

## 错误处理

### 异常命名
- 自定义异常应以 `Error` 结尾
- 例如: `DataProviderError`, `ValidationError`

### 错误消息
- 错误消息应清晰、具体，包含上下文信息
- 使用中文或英文，保持语言一致性

## 配置管理

### 环境变量
- 使用 `VPRISM_` 前缀
- 例如: `VPRISM_API_KEY`, `VPRISM_CACHE_SIZE`

### 配置文件
- 使用 TOML 或 YAML 格式
- 文件名: `vprism.toml` 或 `vprism.yaml`

## 版本控制

### 提交消息
- 使用 [Conventional Commits](https://www.conventionalcommits.org/)
- 格式: `type(scope): description`
- 例如: `feat(providers): add AlphaVantage provider`

### 分支命名
- 功能分支: `feature/short-description`
- 修复分支: `fix/issue-description`
- 文档分支: `docs/update-description`

## 性能考虑

### 缓存策略
- 使用多级缓存架构
- 合理设置TTL值
- 考虑内存和磁盘空间平衡

### 并发处理
- 使用异步编程模式
- 合理设置并发限制
- 实现熔断器模式

## 代码示例

### 正确的提供商实现示例
```python
# vprism/infrastructure/providers/akshare.py

class AkShare(DataProvider):
    """AkShare数据提供商实现。"""
    
    def __init__(self):
        super().__init__("akshare", auth_config, rate_limit)
```

### 正确的导入示例
```python
# 正确的导入方式
from vprism.infrastructure.providers import YFinance, AkShare, AlphaVantage
from vprism.infrastructure.providers.factory import ProviderFactory

# 使用示例
yahoo = YFinance()
akshare = AkShare()
```

## 检查工具

项目使用以下工具确保代码质量：
- **ruff**: 代码格式化和lint检查
- **mypy**: 类型检查
- **pytest**: 单元测试
- **pre-commit**: 提交前检查

## 更新记录

- **2025-07-24**: 添加提供商命名规范，移除冗余的"Provider"后缀