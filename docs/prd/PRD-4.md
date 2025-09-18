PRD-4 质量度量与缺口重复检测 (Quality Metrics & Gap/Duplicate Detection)

Goal
: 捕获并量化数据完整性/一致性核心指标，为回测可信提供闸门。

Scope
Must:
- quality_metrics 表(date,market,supplier_symbol,metric,value,status,run_id,created_at)
- GapDetector: 依据交易日日历检测缺失日期 (expected vs actual)
- DuplicateDetector: (symbol,market,date) 重复计数
- Completeness 计算: gap_ratio = (expected-actual)/expected
- CLI: quality report --market cn --date 2024-09-10 (初期仅 gap_ratio 与 duplicate_count)
Should:
- WARN/FAIL 阈值分类 status
- 缺口补全建议列表 (待 fetch 批命令输入)
- Freshness (ingest_lag_minutes) 与 provider_error_rate 汇总 (Phase 2)
Could:
- 趋势输出最近 N 日 metric sparkline
Out of Scope:
- 漂移统计(Z-score) (PRD-9)
- 对账差异指标(PRD-6)

Data Model (DuckDB)
quality_metrics:
  date DATE NOT NULL
  market TEXT NOT NULL
  supplier_symbol TEXT NULL
  metric TEXT NOT NULL
  value DOUBLE NOT NULL
  status TEXT NOT NULL
  run_id TEXT NOT NULL
  created_at TIMESTAMP NOT NULL
  PRIMARY KEY(date,market,metric,run_id,supplier_symbol)

Status Semantics
- OK: within threshold
- WARN: approaching (>= warn_floor && < fail_threshold)
- FAIL: >= fail_threshold triggers gate

Threshold Config (示例初始值)
- gap_ratio: warn>=0.002 fail>=0.005
- duplicate_count: warn>=1 fail>=3 (市场级)

Algorithm (GapDetector)
1 获取交易日日历(days[]) within [start,end]
2 查询 raw_ohlcv distinct dates for symbol set
3 expected=len(days); actual=len(observed); gap_ratio 计算
4 生成 metric 行 per (symbol?) 初期按市场聚合 + top missing symbols 列表

Algorithm (DuplicateDetector)
SELECT symbol, market, date, COUNT(*) c FROM raw GROUP BY ... HAVING c>1
记录 duplicate_count metric (市场级与 symbol 级可配置)

CLI Report 输出示例 (table)
metric | value | status | threshold_info
gap_ratio | 0.003 | WARN | warn>=0.002 fail>=0.005
duplicate_count | 2 | WARN | warn>=1 fail>=3

Testing Strategy
- 制造缺 3 日: gap_ratio 正确
- 制造重复行: duplicate_count 捕获
- 阈值边界测试 (exact warn/fail)
- 多 metric 混合输出排序 (按严重度)

Open Questions
- 是否对 gap 拆分为前缀 vs 中间 vs 尾部? (初期不区分)
- duplicate 是否按 batch 维度统计? (初期市场级聚合)
- run_id 生成策略 (UUID v4)

Metrics Export (Later)
- quality_gap_ratio{market}
- quality_duplicate_count{market}
- quality_ingest_lag_minutes{market} (Phase 2)
- quality_provider_error_rate{market} (Phase 2)

Acceptance Criteria
- 人工构造缺失/重复场景全部被捕捉
- 阈值逻辑准确分类 OK/WARN/FAIL
- CLI 输出含运行时间与 run_id
- 覆盖率≥80%

Risks & Mitigations
- 日历不准确 → 初期只支持 CN 固定表
- 大量 symbol 行聚合成本 → 初期市场级聚合 + 采样 top N
- 阈值过敏感 → 提供配置 + 文档化默认

Rollout Plan
Phase 1: gap_ratio + duplicate_count + CLI 报告
Phase 2: ingest_lag & provider_error_rate 汇总
Phase 3: top missing symbols & sparkline 可视

Next Steps
1 实现 gap_detector(api)
2 实现 duplicate_detector(api)
3 写入 quality_metrics + 阈值分类函数
4 CLI quality report 渲染
