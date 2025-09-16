PRD-6 对账服务 (Reconciliation Service)

Goal
: 采样对比多数据源(akshare vs yfinance) 核心字段差异，检测数据源漂移。

Scope
Must:
- ReconciliationService.reconcile(symbols, market, date_range) -> ReconcileResult
- 采样策略: uniform sample N (默认50) from 输入 symbols
- 字段差异: close_bp_diff = (close_a - close_b)/close_b*10000 bp; volume_ratio = volume_a/volume_b (guard div0)
- 结果分类: PASS / WARN / FAIL (阈值: |close_bp_diff| warn>=5 fail>=10; volume_ratio 偏离 warn>=1.2 fail>=1.5)
- 统计输出: pass_count,warn_count,fail_count,p95_close_bp_diff
- DuckDB 表 reconciliation_runs(run_id,market,start,end,source_a,source_b,sample_size,created_at,pass,warn,fail,p95_bp_diff)
- 明细表 reconciliation_diffs(run_id,symbol,date,close_a,close_b,close_bp_diff,volume_a,volume_b,volume_ratio,status)
Should:
- CLI reconcile run --market cn --sample-size 50 --start 2024-01-01 --end 2024-03-01
- 阈值可配置 (config 对象)
Could:
- 结果缓存 (同参数24h 内命中)
- 异常符号 TopN 导出 CSV
Out of Scope:
- 全量对账 (性能负担)
- tick 级对账

Algorithm
1 采样 symbols -> S
2 对每个 Provider 获取相同日期范围数据 (日线)
3 对齐日期 (内连接) 计算差异 close_bp_diff / volume_ratio
4 按阈值分类 status
5 聚合统计写 reconciliation_runs + 明细写 diffs
6 返回结果对象 (包含聚合 + 前若干 fail 样本)

Metrics (Later)
- reconciliation_fail_rate
- reconciliation_avg_bp_diff

Error Handling
- 源数据缺失 (某Provider无数据) -> 标记 missing_source_x = True; 该 symbol 全 FAIL
- 数据长度不匹配 -> 仅对齐交集日期, gap 进入 missing 统计

Testing Strategy
- 构造恒等数据 → 全 PASS
- 单符号系统性偏差 +10bp → WARN/FAIL 分类命中
- volume 差异 > 阈值分类
- 一方无数据 → 全 FAIL + missing 标记
- 混合场景统计计数正确

Open Questions
- 是否需要对齐企业行为调整后价格 (当前使用 raw close)
- 是否需要过滤节假日 (使用交易日日历) (Must for准确)
- 采样策略是否增加 stratified by market segment (当前不做)

Acceptance Criteria
- FAIL/WARN 按阈值分类准确
- p95_close_bp_diff 计算正确 (测试给定分布)
- CLI 输出聚合+前10差异行
- 覆盖率≥80%

Risks & Mitigations
- Provider 速率限制 → 采样 + 并发限制
- 差异噪音(货币/时区) → 要求统一 canonical 时间/不做跨币种对账
- 业务误用对账价(复权 vs 未复权) → 文档强调使用 raw close

Rollout Plan
Phase 1: 核心差异 & CLI
Phase 2: 配置化阈值 & 缓存
Phase 3: 增加指标导出与趋势分析

Next Steps
1 定义 Reconciliation 数据模型
2 实现差异计算 + 分类函数
3 写入表结构 + 测试
4 CLI 接口集成
