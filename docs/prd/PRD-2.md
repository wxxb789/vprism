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
- Ingestion API ingest(records: Iterable[RawRecord], provider:str, market:str) 将通过校验的记录写入 raw_ohlcv，并补充 batch_id(UUIDv4) 与 ingest_time
- RawRecord 模型 (supplier_symbol,timestamp,open,high,low,close,volume,provider)
- DuckDB 表 raw_ohlcv(supplier_symbol,market,ts,open,high,low,close,volume,provider,batch_id,ingest_time)
- 基础校验: 字段非空(open..close,volume允许0), 数值有限, OHLC 关系 low<=open/close<=high, volume>=0
- 时间校验: 同 batch 内 timestamp 严格递增或非降序 (configurable)
Should:
- 重复行检测 (supplier_symbol,market,ts) 去重策略 (忽略写入计为 duplicate_count)
- 配置对象 IngestionConfig(max_batch_rows, enforce_monotonic_ts, allow_duplicate)
- 性能计时 metrics stub
- Null & 校验失败行统计并剔除写入
- IngestionResult {written_rows,rejected_rows,fail_reasons[],batch_id,duration_ms}
- 结构化错误类型: ValidationError(detail=list[FieldIssue])
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
R6 Duplicate 策略（Milestone 1）: 如果存在相同 (symbol,market,ts) 且不同 batch → 允许; 同 batch 冲突 → 保留首行

Algorithm (ingest)
1 start timer; gen batch_id
2 iterate records: validate -> 将记录区分为 valid_rows / rejected_rows
3 （Milestone 1）deduplicate (in-memory set) if configured
4 bulk insert (DuckDB executemany) inside transaction
5 （Milestone 1）produce IngestionResult + metrics emit stub

Metrics (Later Prometheus Bridge)
- ingestion_rows_total{provider,market}
- ingestion_rejected_total{reason}
- ingestion_duration_ms_histogram
- ingestion_duplicates_total

Error Model（Milestone 1）
ValidationError: issues=[{field, code, message, value?}]
IngestionConfigError: 配置非法时抛出

Performance Targets
- 10k 行 batch 校验+写入 < 500ms 本地
- 内存占用 < 30MB (10k 记录暂存)

Testing Strategy
Milestone 0
- test_valid_batch_all_written
- test_missing_field_rejected
- test_ohlc_violation_rejected
- test_volume_negative_rejected
- test_timestamp_non_monotonic_when_enforced
- test_timestamp_non_monotonic_not_enforced
Milestone 1
- test_duplicate_same_batch_deduped
- test_partial_rejection_counts
Milestone 2
- test_large_batch_performance (标记 perf)

Open Questions
- volume 缺失是否填 0 或拒绝 (假设填 0 并加 flag?)
- high/low 颠倒数据是否自动交换 (当前：拒绝)
- 是否需要 early abort 当拒绝率 > X% (默认不做)
- 允许浮点精度保留还是四舍五入 (默认保持原值)

Acceptance Criteria
Milestone 0
- 违反基础校验/时间规则的记录全部拒绝写入，写入行数 = 输入 - rejected
- 覆盖率≥80%，基础校验与异常分支具备单测
- 执行 ingestion 示例日志包含 batch_id 与写入行数
Milestone 1
- 提供 rejected_rows 统计与 fail_reasons 聚合
- IngestionResult 输出 written_rows/rejected_rows/fail_reasons/batch_id/duration_ms

Risks & Mitigations
- 大批内存峰值 → 流式校验+缓写 (后续优化)
- 时间校验耗时 → 仅单 pass 比对前值
- 浮点不精确影响比较 → 使用 <=/>= 容差阈值 epsilon=1e-12

Rollout Plan
Milestone 0: Validated write path 到 raw_ohlcv（完成 Must 范围）
  - 最终确定 RawRecord/raw_ohlcv schema 并创建表
  - 实现 ingest() 流程，执行基础字段/时间校验，仅将通过校验的记录持久化
  - 覆盖“全部通过 / 校验失败 / 时间逆序”等基础场景的测试
Milestone 1: Duplicate 检测/索引、结构化错误模型 & Metrics hook
Milestone 2: 并发/分片 & backoff 重试

Next Steps
Milestone 0
1 定义 RawRecord 数据模型与 raw_ohlcv 表 schema
2 实现基础校验器 validator(record)->list[Issue]
3 编写 ingestion 事务写入函数 + 基础场景 tests
Milestone 1
4 扩展 ValidationIssue/IngestionResult & rejected_rows 聚合
5 引入 IngestionConfig + duplicate 逻辑
