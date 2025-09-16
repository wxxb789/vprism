PRD-2 原始数据采集与基础校验 (Raw Ingestion & Validation)

Goal
: 提供统一 Provider→raw DuckDB 写入与最小必需质量闸门，防止脏数据进入下游。

Background
当前直接查询返回给调用者，缺少持久化与结构化校验；无 batch 追踪、无失败分类。

Problem Statement
- 无 raw 层 → 不可重放/重算
- 缺批次与 lineage → 难审计
- 缺基础校验 → 脏行潜入回测
- 缺结构化失败报告 → 排错低效

Scope
Must:
- Ingestion API ingest(records: Iterable[RawRecord], provider:str, market:str) -> IngestionResult
- RawRecord 模型 (supplier_symbol,timestamp,open,high,low,close,volume,provider)
- DuckDB 表 raw_ohlcv(supplier_symbol,market,ts,open,high,low,close,volume,provider,batch_id,ingest_time)
- 基础校验: 字段非空(open..close,volume允许0), OHLC一致 open<=high>=low<=high, low<=open/close<=high, volume>=0
- 时间校验: 同 batch 内 timestamp 严格递增或非降序 (configurable)
- Null & 校验失败行统计并剔除写入
- IngestionResult {written_rows,rejected_rows,fail_reasons[],batch_id,duration_ms}
- batch_id 生成 UUIDv4
- 结构化错误类型: ValidationError(detail=list[FieldIssue])
- 单元测试: 通过/失败/部分拒绝/时间逆序/极值边界
Should:
- 重复行检测 (supplier_symbol,market,ts) 去重策略 (忽略写入计为 duplicate_count)
- 配置对象 IngestionConfig(max_batch_rows, enforce_monotonic_ts, allow_duplicate)
- 性能计时 metrics stub
Could:
- 并行分片校验 (后期)
- Provider 自动重试(指数退避 3 次)
Out of Scope:
- 缺口检测 (PRD-4)
- 对账 (PRD-6)
- 复权 (PRD-3)

Data Model (DuckDB)
raw_ohlcv:
  supplier_symbol TEXT NOT NULL
  market TEXT NOT NULL
  ts TIMESTAMP NOT NULL
  open DOUBLE
  high DOUBLE
  low DOUBLE
  close DOUBLE
  volume DOUBLE
  provider TEXT NOT NULL
  batch_id TEXT NOT NULL
  ingest_time TIMESTAMP NOT NULL
PRIMARY KEY(supplier_symbol,market,ts,batch_id)

Indexes (Should)
- CREATE INDEX raw_symbol_ts ON raw_ohlcv (supplier_symbol, market, ts);

Validation Rules
R1 必填: supplier_symbol, market, ts, open, high, low, close
R2 数值范围: open,high,low,close 为有限数 (非 NaN/Inf)
R3 OHLC 关系: low <= open <= high AND low <= close <= high AND low <= high
R4 Volume>=0 (缺失→0 可配置?)
R5 Timestamp 单调: ts[i] >= ts[i-1] (enforce_monotonic_ts=True)
R6 Duplicate 策略: 如果存在相同 (symbol,market,ts) 且不同 batch → 允许; 同 batch 冲突 → 保留首行

Algorithm (ingest)
1 start timer; gen batch_id
2 iterate records: validate -> accumulate valid_rows / rejected_rows
3 deduplicate (in-memory set) if configured
4 bulk insert (DuckDB executemany) inside transaction
5 produce IngestionResult + metrics emit stub

Metrics (Later Prometheus Bridge)
- ingestion_rows_total{provider,market}
- ingestion_rejected_total{reason}
- ingestion_duration_ms_histogram
- ingestion_duplicates_total

Error Model
ValidationError: issues=[{field, code, message, value?}]
IngestionConfigError: 配置非法时抛出

Performance Targets
- 10k 行 batch 校验+写入 < 500ms 本地
- 内存占用 < 30MB (10k 记录暂存)

Testing Strategy
- test_valid_batch_all_written
- test_missing_field_rejected
- test_ohlc_violation_rejected
- test_volume_negative_rejected
- test_timestamp_non_monotonic_when_enforced
- test_timestamp_non_monotonic_not_enforced
- test_duplicate_same_batch_deduped
- test_large_batch_performance (标记 perf)
- test_partial_rejection_counts

Open Questions
- volume 缺失是否填 0 或拒绝 (假设填 0 并加 flag?)
- high/low 颠倒数据是否自动交换 (当前：拒绝)
- 是否需要 early abort 当拒绝率 > X% (默认不做)
- 允许浮点精度保留还是四舍五入 (默认保持原值)

Acceptance Criteria
- 任一规则违反对应 rejected_rows 递增 & fail_reasons 聚合
- 成功写入行数 = 输入 - rejected
- 覆盖率≥80%，异常分支均被测试
- 执行 ingestion 示例日志包含 batch_id & stats

Risks & Mitigations
- 大批内存峰值 → 流式校验+缓写 (后续优化)
- 时间校验耗时 → 仅单 pass 比对前值
- 浮点不精确影响比较 → 使用 <=/>= 容差阈值 epsilon=1e-12

Rollout Plan
Phase 1: 同步单线程实现 + 基础规则
Phase 2: Duplicate 检测/索引 & Metrics hook
Phase 3: 并发/分片 & backoff 重试

Next Steps
1 定义 RawRecord/ValidationIssue/IngestionResult 数据模型
2 实现校验器 validator(record)->list[Issue]
3 编写 ingestion 事务写入函数 + tests
4 引入 IngestionConfig + duplicate 逻辑
