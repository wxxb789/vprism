PRD-0 基础测试与 Schema 基线

Goal
: 建立 raw/normalized 占位 schema 与测试框架

Scope
- Must: raw_schema(supplier_symbol,timestamp,open,high,low,close,volume,provider), normalization_schema(+market,tz_offset,currency,c_symbol)
- Must: schema assertion helpers
- Must: provider stub + ingestion sample test
- Should: DuckDB connection factory
- Could: lineage table stub(id,batch_id,source_provider,ingest_time)

Non-Goals
- 复权计算
- 质量指标写入
- 对账逻辑

Success Metrics
- pytest 全绿 & 覆盖率≥50%
- mypy/ruff 0 error
- 示例 ingestion 测试耗时<2s

Acceptance Criteria
- schema 定义集中单模块并具备 create_ddl() 或 migration 函数
- 失败字段缺失测试能捕获并抛出结构化异常
- provider stub 可注入假数据行并通过验证写入 raw 表

Risks & Mitigations
- 过早扩展列 → 仅保留核心列, 后续 PRD 扩展
- DuckDB 锁写风险 → 单线程写 + 测试内临时库

Open Questions
- 行为: batch_id 生成策略(默认 UUID)
- 时间: tz_offset 计算方式(默认 Asia/Shanghai 固定)

Next Steps
1. 定义 schema 模块 draft
2. 编写 schema 校验测试
3. 实现 provider stub 与 ingestion 示例
