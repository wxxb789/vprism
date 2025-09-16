PRD-5 CLI v1 核心命令 (Data & Quality CLI)

Goal
: 提供可脚本化、一致、可扩展的首版命令行工具集支持数据抓取与质量洞察。

Scope
Must:
- 基础命令组: data / quality / symbol / ca
- data fetch --asset stock --market cn --symbols 000001,000002 --start 2020-01-01 --end 2020-12-31 --adjustment all --format table
- data normalize --batch <batch_id>
- data adjust --symbol 000001 --market cn --start 2020-01-01 --end 2020-12-31 --mode qfq|hfq|all
- quality report --market cn --date 2024-09-10
- symbol resolve 000001 --market cn --asset stock
- ca ingest --market cn --since 2020-01-01
- 全局参数: --format (table|jsonl|csv|parquet), --output <path>, --log-level, --no-color
- 退出码语义: 0 OK,10 VALIDATION,20 PROVIDER,30 DATA_QUALITY,40 RECONCILE,50 SYSTEM
- 统一错误渲染: code,message,context(trace_id optional)
- Rich/简单表渲染 (table), jsonl 流模式按行输出
Should:
- 自动补全 shell completion (bash/zsh/fish)
- 进度条 (fetch 批次) 与 --no-progress
- --symbols-from <file>
Could:
- parquet 输出 (pyarrow 可用时)
- metrics 命令导出当前内部计数
Out of Scope:
- 插件动态加载 (PRD-9)
- 对账 CLI (PRD-6)

Design
- Typer 或 click + Rich 渲染 (保持最小依赖)
- Command 层不含业务逻辑，仅调用 service facade
- OutputFormatter 接口 + 实现(TableFormatter/CSVFormatter/JSONLFormatter)
- ErrorHandler 中央化: 捕获已知 DomainError -> 退出码映射

Testing Strategy
- test_fetch_basic_jsonl 输出行数与字段
- test_fetch_invalid_symbol 返回退出码10
- test_symbol_resolve_hit/miss
- test_quality_report_table_headers
- test_adjust_modes 输出包含 qfq/hfq 列
- test_cli_exit_codes_mapping
- test_symbols_from_file 解析

Metrics (future hook)
- cli_command_duration_seconds{command}
- cli_command_failures_total{command,code}

Open Questions
- 是否需要颜色可配置 (默认开启, 可 --no-color)
- parquet 支持是否必须 (初期 optional)
- 调整模式 all 是否输出多列 vs 多行 (采用多列)

Acceptance Criteria
- 六大核心命令可用且互不阻塞
- 同一命令错误输出一致格式
- 不提供多余隐藏破坏行为 (幂等运行安全)
- 覆盖率≥70% (命令路径)

Risks & Mitigations
- 过度参数膨胀 → 仅核心, 复杂延后
- I/O 性能差 → jsonl 流式写
- 格式多样化测试负担 → 抽象统一 formatter 接口

Rollout Plan
Phase 1: fetch/resolve/quality core
Phase 2: adjust/ca ingest
Phase 3: polish (completion/progress/parquet)

Next Steps
1 定义 CLI 目录结构 & entry point
2 Formatter 接口 + 最小实现
3 集成 symbol + ingestion + adjustment 服务调用
4 错误映射与测试
