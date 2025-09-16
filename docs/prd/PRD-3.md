PRD-3 企业行为与初始复权引擎 (Corporate Actions & Adjustment Engine)

Goal
: 构建可复现的企业行为(corporate actions)存储与前/后复权价格计算，支持回测一致性。

Background
回测需要对拆分/股息/配股等事件进行价格调整；目前缺事件数据结构与因子计算封装。

Problem Statement
- 企业行为缺失 → 回测收益失真
- 无因子版本 → 历史结果不可追溯
- 多事件叠加顺序不确定 → 计算不稳定

Scope
Must:
- corporate_actions 表( market,supplier_symbol,event_type,effective_date,dividend_cash,split_ratio,raw_payload,ingest_time,source,batch_id )
- 支持事件类型: dividend, split (扩展: bonus, rights future)
- AdjustmentEngine.compute(symbol, market, start,end, mode=qfq|hfq|none)
- 价格因子表 adjustments (symbol,market,date,adj_factor_qfq,adj_factor_hfq,version,build_time,source_events_hash)
- 计算策略: 按日期逆序/正序累计因子 (qfq 累乘未来拆分/股息影响)
- API 返回: {date, close_raw, close_qfq, close_hfq, adj_factor_qfq, adj_factor_hfq}
- version: 以事件集合 hash + 算法版本号组合
- 缺失事件标志: action_gap_flag
- 单元测试覆盖：单事件/多事件/股息+拆分类/无事件透传
Should:
- 事件合并逻辑 (同日多事件合并为单计算单元)
- 因子缓存重用 (memoization)
- CLI: ca ingest / ca apply / data adjust
Could:
- 并行批量因子构建
- 支持高级事件 rights, bonus
Out of Scope:
- 实时 tick 级调整
- 外部 FX 影响

Data Model (DuckDB)
corporate_actions:
  market TEXT
  supplier_symbol TEXT
  event_type TEXT
  effective_date DATE
  dividend_cash DOUBLE NULL
  split_ratio DOUBLE NULL
  raw_payload JSON NULL
  source TEXT
  batch_id TEXT
  ingest_time TIMESTAMP
  PRIMARY KEY(market,supplier_symbol,event_type,effective_date,batch_id)

adjustments:
  market TEXT
  supplier_symbol TEXT
  date DATE
  adj_factor_qfq DOUBLE
  adj_factor_hfq DOUBLE
  version TEXT
  build_time TIMESTAMP
  source_events_hash TEXT
  PRIMARY KEY(market,supplier_symbol,date,version)

Computation Overview
1 拉取 raw close 序列 + 相关事件(<=end)
2 生成事件序列按 effective_date 升序
3 构建后复权(hfq): 从最早到最新累乘拆分 & 调整股息 (若采用加权法)
4 前复权(qfq): 以最新价格为基准逆向回推 (或直接使用 hfq 因子倒推)
5 写 adjustments 因子行 (每日期一个)
6 合并输出 adjusted close 列

Adjustment Formulas (简化)
- split_ratio r: 价格除以 r, 因子乘以 r (hfq 累乘)
- dividend_cash d: qfq 常见处理 (price_{prev} = price_{curr} + d) 影响前序因子
  (实际公式需确认：暂采用 国内常规前复权算法: 前价 = 后价 * (前收盘价 - 现金红利) / 前收盘价)

Versioning
algorithm_version = 1 (初始)
source_events_hash = sha256(sorted(events projection))
version = f"1:{source_events_hash[:12]}"

Error Handling
- 缺少价格序列 → Raise AdjustmentInputError
- 事件重叠冲突 → 标记 conflict_flag 并跳过冲突事件 (Should)

Metrics (Later)
- adjustment_compute_duration_ms
- adjustment_gap_symbols_total
- adjustment_version_count

Testing Strategy
- 单拆分: close=100, split 2:1 -> hfq 因子=2
- 单股息: close=10, dividend=1 -> qfq 之前价格回推验证
- 拆分+股息组合顺序不变性测试
- 无事件: 因子=1 输出等于原始
- 多事件同日合并测试
- 版本哈希变更测试(添加事件)

Open Questions
- 股息与价格回推采用精确国内公式还是近似? (需确认)
- 多币种股息是否需要汇率换算? (当前 No)
- 是否需要对事件缺失做外部补全? (后续 Could)

Acceptance Criteria
- 事件存在时 adjusted close 与预计算基准用例匹配
- 因子写入行数=价格序列长度
- version 可复现: 删除再计算得相同 version
- 覆盖率≥85% (计算/分支)

Risks & Mitigations
- 事件数据不全 → action_gap_flag + metrics
- 算法误实现 → 基准回测用例对照
- 多事件同日复杂 → 初期合并仅拆分+股息简单加权

Rollout Plan
Phase 1: dividend+split 支持 + hfq/qfq 因子
Phase 2: 事件合并 & 缓存重用
Phase 3: 高级事件扩展 + CLI 优化

Next Steps
1 定义事件与因子数据模型
2 实现 compute pipeline (单 symbol)
3 添加组合事件测试用例
4 CLI 接入 (后续 PRD-5)
