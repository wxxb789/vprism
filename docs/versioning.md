# vprism 文档网站和版本管理

## 文档网站搭建

### MkDocs配置

创建 `mkdocs.yml` 配置文件：

```yaml
site_name: vprism Documentation
site_description: 下一代个人金融数据平台
site_author: vprism Team
site_url: https://docs.vprism.com

repo_name: vprism/vprism
repo_url: https://github.com/vprism/vprism
edit_uri: edit/main/docs/

theme:
  name: material
  logo: assets/logo.png
  favicon: assets/favicon.ico
  palette:
    - scheme: default
      primary: blue
      accent: blue
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - scheme: slate
      primary: blue
      accent: blue
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.top
    - search.highlight
    - search.share
    - content.code.annotate
    - content.code.copy

nav:
  - 首页: index.md
  - 快速开始: quickstart.md
  - 用户指南:
    - 安装指南: installation.md
    - Python库API: api/library.md
    - Web服务API: api/web.md
    - MCP服务API: api/mcp.md
  - 部署指南:
    - 部署概述: deployment/README.md
    - Docker部署: deployment/docker.md
    - Kubernetes部署: deployment/kubernetes.md
    - 生产环境配置: deployment/production.md
  - 高级主题:
    - 性能优化: advanced/performance.md
    - 数据质量保证: advanced/data-quality.md
    - 扩展开发: advanced/extensions.md
  - 故障排除:
    - 常见问题: troubleshooting.md
    - FAQ: faq.md
  - 参考:
    - 配置选项: reference/configuration.md
    - API参考: reference/api-reference.md
    - 错误代码: reference/error-codes.md

extra:
  social:
    - icon: fontawesome/brands/github
      link: https://github.com/vprism/vprism
    - icon: fontawesome/brands/discord
      link: https://discord.gg/vprism
    - icon: fontawesome/brands/twitter
      link: https://twitter.com/vprism_finance
  version:
    provider: mike
    default: latest

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            show_source: false
            show_root_heading: true
            show_root_toc_entry: false
            show_if_no_docstring: true
            show_signature_annotations: true
  - minify:
      minify_html: true
      minify_js: true
      minify_css: true

markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - tables
  - footnotes
```

### 主题定制

创建 `docs/stylesheets/extra.css`：

```css
:root {
  --md-primary-fg-color: #1976d2;
  --md-accent-fg-color: #2196f3;
}

[data-md-color-scheme="slate"] {
  --md-primary-fg-color: #2196f3;
  --md-accent-fg-color: #64b5f6;
}

.md-header {
  background: linear-gradient(135deg, #1976d2 0%, #2196f3 100%);
}

.md-typeset .admonition {
  font-size: 0.9rem;
}

.md-typeset code {
  background-color: rgba(0, 0, 0, 0.05);
  border-radius: 3px;
  padding: 2px 4px;
}
```

### 本地开发环境

```bash
# 安装MkDocs
pip install mkdocs mkdocs-material mkdocstrings[python] mike

# 本地预览
cd docs
mkdocs serve

# 构建静态站点
mkdocs build --clean
```

### 自动化部署到GitHub Pages

创建 `.github/workflows/docs.yml`：

```yaml
name: Documentation

on:
  push:
    branches: [main, dev]
  pull_request:
    branches: [main]

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: 3.11

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install mkdocs mkdocs-material mkdocstrings[python] mike
          pip install -e .

      - name: Build documentation
        run: mkdocs build --strict

      - name: Deploy to GitHub Pages
        if: github.ref == 'refs/heads/main'
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: site
```

## 版本管理策略

### Semantic Versioning

采用语义化版本号：MAJOR.MINOR.PATCH

- MAJOR：不兼容的API变更
- MINOR：向下兼容的功能新增  
- PATCH：向下兼容的问题修复

### 版本分支策略

```
main (v1.0.0)
├── dev/v1.1.0 (新功能开发)
├── hotfix/v1.0.1 (紧急修复)
└── feature/new-provider (新提供商支持)
```

### 版本发布流程

1. 创建版本分支
```bash
git checkout -b release/v1.1.0
git push origin release/v1.1.0
```

2. 更新版本号
```bash
# pyproject.toml
[project]
version = "1.1.0"

# vprism/__init__.py
__version__ = "1.1.0"
```

3. 更新文档版本
```bash
# 使用mike管理文档版本
mike deploy 1.1.0 latest --push
mike set-default latest --push
```

### 变更日志管理

创建 `CHANGELOG.md` 模板：

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New feature descriptions

### Changed
- Changed feature descriptions

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security improvements

## [1.0.0] - 2024-07-21

### Added
- Initial release of vprism
- Support for US, CN, HK markets
- Multi-provider data sources
- Caching system
- RESTful API
- MCP integration
```

## 自动化版本管理

### 版本发布脚本

创建 `scripts/release.sh`：

```bash
#!/bin/bash

set -e

VERSION=$1
if [ -z "$VERSION" ]; then
    echo "Usage: ./release.sh [version]"
    exit 1
fi

# 验证版本号格式
if [[ ! $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Invalid version format. Use semantic versioning (e.g., 1.0.0)"
    exit 1
fi

# 更新版本号
sed -i "s/version = \".*\"/version = \"$VERSION\"/" pyproject.toml
sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" src/vprism/__init__.py

# 运行测试
pytest tests/ -v

# 构建包
python -m build

# 更新文档版本
mike deploy $VERSION --push

# 创建Git标签
git add pyproject.toml src/vprism/__init__.py CHANGELOG.md
git commit -m "Release version $VERSION"
git tag -a v$VERSION -m "Release version $VERSION"
git push origin main --tags

echo "✅ Release $VERSION completed successfully!"
```

### 预发布版本管理

#### Beta版本发布
```bash
# 创建预发布版本
./scripts/release.sh 1.1.0b1

# 文档预发布版本
mike deploy 1.1.0b1 --push
```

#### 候选版本发布
```bash
# 创建候选版本
./scripts/release.sh 1.1.0rc1
```

### 版本兼容性矩阵

创建版本兼容性文档：

| vprism版本 | Python版本 | 依赖要求 | 新功能 |
|------------|------------|----------|--------|
| 1.0.x | 3.8+ | pandas>=1.3, httpx>=0.20 | 基础功能 |
| 1.1.x | 3.9+ | pandas>=1.5, httpx>=0.24 | MCP支持 |
| 1.2.x | 3.10+ | pandas>=2.0, httpx>=0.25 | WebSocket实时数据 |

### 弃用策略

#### 弃用通知格式
```python
import warnings

def deprecated_function(*args, **kwargs):
    warnings.warn(
        "This function is deprecated and will be removed in v2.0. "
        "Use new_function() instead.",
        DeprecationWarning,
        stacklevel=2
    )
    return new_function(*args, **kwargs)
```

### 版本迁移指南

创建迁移指南文档：

#### v1.0 → v1.1 迁移指南

1. API变更
```python
# v1.0 (旧)
from vprism import stock
data = stock.get_price("AAPL")

# v1.1 (新)
import vprism
data = vprism.get("AAPL")
```

2. 配置变更
```python
# v1.0 (旧)
config = {
    "cache_size": 1000,
    "cache_ttl": 3600
}

# v1.1 (新)
config = {
    "cache": {
        "memory_size": 1000,
        "ttl": 3600
    }
}
```

### 版本分支保护规则

#### GitHub分支保护
```yaml
# .github/settings.yml
branches:
  main:
    protection:
      required_status_checks:
        strict: true
        contexts:
          - tests
          - docs-build
      enforce_admins: false
      required_pull_request_reviews:
        required_approving_review_count: 2
      restrictions:
        users: []
        teams: [maintainers]
```

### 自动化测试矩阵

#### 多版本测试
```yaml
# .github/workflows/ci.yml
strategy:
  matrix:
    python-version: ["3.8", "3.9", "3.10", "3.11"]
    os: [ubuntu-latest, windows-latest, macos-latest]
    exclude:
      - python-version: "3.8"
        os: macos-latest  # 特定组合排除
```

### 文档自动化工具

#### API文档自动生成
```python
# scripts/generate_api_docs.py
import inspect
from vprism.core.client import VPrismClient

client = VPrismClient()

# 生成API方法文档
for name, method in inspect.getmembers(client, predicate=inspect.ismethod):
    if not name.startswith('_'):
        docstring = inspect.getdoc(method)
        parameters = inspect.signature(method).parameters
        # 生成Markdown格式的API文档
```

#### 变更日志自动生成
```python
# scripts/generate_changelog.py
from git import Repo
import re

repo = Repo('.')
commits = list(repo.iter_commits('main', max_count=100))

changelog_entries = {
    'added': [],
    'changed': [],
    'fixed': [],
    'security': []
}

for commit in commits:
    if commit.message.startswith('feat:'):
        changelog_entries['added'].append(commit.message[5:].strip())
    elif commit.message.startswith('fix:'):
        changelog_entries['fixed'].append(commit.message[4:].strip())
```

### 版本通知机制

#### 新版本通知
```python
# vprism/utils/version_check.py
import requests

def check_for_updates(current_version):
    try:
        response = requests.get(
            "https://api.github.com/repos/vprism/vprism/releases/latest",
            timeout=5
        )
        latest_version = response.json()['tag_name'].lstrip('v')
        if latest_version > current_version:
            return {
                'update_available': True,
                'current': current_version,
                'latest': latest_version
            }
    except Exception:
        pass
    return {'update_available': False}
```

通过以上完整的文档网站搭建和版本管理策略，可以确保vprism项目的文档始终保持最新、准确且易于维护，同时为用户提供清晰的版本升级路径和兼容性指导。