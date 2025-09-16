PRD-7 可观测性与错误分层 (Observability & Error Taxonomy)

Goal
: 统一错误分类与指标输出，支持运维定位与 SLO 评估。

Scope
Must:
- 错误枚举 ErrorCode (VALIDATION, ROUTING, PROVIDER, DATA_QUALITY, RECONCILE, SYSTEM)
- DomainError 基类: code, message, layer, retryable, context(dict)
- MetricsCollector: record_query(provider, latency_ms, success|fail, error_code?)
- Prometheus 端点 /metrics (FastAPI 集成)
- 指标: query_latency_ms(histogram), query_fail_total{error_code}, provider_error_rate, symbol_normalization_hit_rate (暴露已有 counters)
- trace_id 生成 (uuid4) 注入日志上下文
- 结构化日志: JSON formatter (timestamp, level, msg, trace_id, code?, provider?, symbol?)
Should:
- Slow query log (p95 超阈值记录)
- 分层 error->exit code 映射 CLI 复用
Could:
- OpenTelemetry exporter (扩展点)
Out of Scope:
- 分布式 tracing 全链路可视化 (后续)

Logging Policy
- INFO: 成功批次摘要 / 阈值切换
- WARN: 接近阈值质量指标 / 重试
- ERROR: 失败最终状态(含 code)
- DEBUG: 可通过环境变量启用

Metrics Naming Conventions
- vprism_query_latency_ms_bucket
- vprism_query_fail_total{code}
- vprism_provider_requests_total{provider,code}
- vprism_symbol_normalization_total{status}

Testing Strategy
- 触发各类错误枚举断言日志 code 字段存在
- 人造两次失败一次成功 -> provider_error_rate 计算
- query latency 直方图 bucket 计数递增
- trace_id 在同一次请求链多日志复用

Open Questions
- 是否需要将 batch ingest 也纳入统一 metrics 接口 (建议 Yes 后续)
- 指标标签 cardinality 上限策略 (provider,symbol 限制 symbol?)

Acceptance Criteria
- /metrics 返回包含核心指标
- 抛出任一 DomainError 日志含 code & trace_id
- CLI 失败退出码与 code 映射正确
- 覆盖率≥75%

Risks & Mitigations
- 指标标签爆炸 → 限制 symbol 不作为高基数标签
- 观测开销影响性能 → 延迟路径使用轻量计数 + 异步聚合 (后续)

Rollout Plan
Phase 1: 错误枚举 + 基础 metrics
Phase 2: 慢查询 & 质量指标接入
Phase 3: OpenTelemetry 可选接入

Next Steps
1 定义 ErrorCode & DomainError
2 MetricsCollector 接口 + 直方图实现
3 FastAPI /metrics 路由
4 测试各类错误路径
