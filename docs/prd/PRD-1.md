PRD-1 符号标准化 (Symbol Normalization Service)

Goal
: 为多来源(akshare / yfinance)与未来扩展提供一致、可审计、可缓存的符号规范化能力，提升查询成功率并降低上游接口差异耦合。

Background
当前用户输入与 Provider 实际参数存在多种前/后缀与市场/资产类型差异；缺集中映射导致：
- 重复实现 / 易遗漏
- 错误 silently fallback 造成错价或空数据
- 无法溯源映射规则演进

Problem Statement
- 缺统一规范: 同一逻辑散落在调用点
- 缺缓存: 重复解析增加延迟/上游压力
- 缺版本化: 规则变更后历史结果不可复现
- 缺可观测: 无命中率/失败模式指标

Scope
Must:
- SymbolService 接口: normalize(raw_symbol, market, asset_type) -> CanonicalSymbol
- 内置最小规则集(股票/基金/指数 基础模式) (示例形式, 待确认实际映射)
- 规则数据结构: Rule(priority,int), pattern(正则/前缀), transform(callable/模板), asset_scope
- 内存LRU缓存 (默认 max_size=10k) + 命中统计
- Phase 1 保持纯内存实现（无外部持久化依赖）
- 结构化失败结果 (UnresolvedSymbolError, 含 diagnostics)
- 规则加载: 内置 (外部 YAML/JSON 支持在后续阶段追加)
- 单元测试 (规则命中 / 未命中 / 缓存命中)
Should:
- 规则热更新 reload() (原子替换)
- 外部 YAML/JSON 规则加载
- 批量规范化 normalize_batch(list[str], market, asset_type) with partial 成功报告
- DuckDB 表 symbol_map (c_symbol, raw_symbol, market, asset_type, provider_hint, rule_id, created_at)
- 统计导出 get_metrics() {hit_rate, miss_count, rule_usage_rank}
Could:
- 前缀感知歧义消解(基于 provider capability)
- 模糊匹配建议 (编辑距离≤2)
Out of Scope:
- 交易所路由决策
- 跨市场合并 (US vs HK 同名)
- 企业行为/复权逻辑

Definitions
- raw_symbol: 用户输入原始字符串
- canonical_symbol(c_symbol): 内部统一标识 (market + 标准化主体 + 可选后缀)，保证幂等
- provider_symbol: 针对特定 provider 的最终参数 (延迟到 provider adapter 级转换，非本 PRD 输出)

Functional Requirements
FR1 normalize 提供确定 & 幂等: 多次调用返回同对象值
FR2 失败时返回结构化错误，不抛裸异常，不返回 None 静默
FR3 命中缓存须递增 hit_counter; miss 进入规则匹配流程
FR4 规则按 priority ASC 执行，首个匹配即终止
FR5 规则可声明 asset_scope(set[AssetType]) & market_scope(set[MarketType])
FR6 服务维持内存命中统计(total_requests/cache_hits/cache_misses/unresolved_count)

Deferred Functional Requirements (Phase 2+)
DFR1 支持批量输入 normalize_batch(list[str], market, asset_type) 并提供 per-item status
DFR2 存储: 首次成功规范化写 symbol_map (INSERT OR IGNORE)
DFR3 reload 调用后新请求使用新规则，旧缓存保留 TTL 到期清空 (初期简化: 全量清空)
DFR4 metrics 输出结构便于 Prometheus 包装 (字典即可)
DFR5 支持外部 YAML/JSON 规则加载并进行安全校验

Non-Functional Requirements
NFR1 平均单 symbol 解析延迟 < 0.3ms (缓存命中)
NFR2 内存占用可控 (< 2MB for 10k entries)
NFR3 无外部网络调用 (纯本地)
NFR4 mypy 严格通过 & 0 ruff 违规
NFR5 测试覆盖 逻辑分支 ≥85%

Proposed Data Model (DuckDB, Phase 2+)
用于批量/审计场景的持久化需求暂缓到 Phase 2，实现时将采用如下结构：
symbol_map:
  c_symbol TEXT NOT NULL
  raw_symbol TEXT NOT NULL
  market TEXT NOT NULL
  asset_type TEXT NOT NULL
  provider_hint TEXT NULL
  rule_id TEXT NOT NULL
  created_at TIMESTAMP NOT NULL
PRIMARY KEY (c_symbol, raw_symbol)

Metrics (in-memory counters)
- total_requests
- cache_hits
- cache_misses
- unresolved_count
- rule_usage{rule_id -> count}
Derived: hit_rate = cache_hits/total_requests

Rule Representation
Rule:
  id: str
  priority: int
  pattern: Literal/Regex/Callable predicate
  transform: Callable(raw)->normalized_core (不含 market 前缀)
  market_scope: set[str] | empty=all
  asset_scope: set[str] | empty=all
  add_prefix: Optional[str]
  add_suffix: Optional[str]

示例规则 (仅示例, 不代表真实映射, 实际需确认)
- CN 股票A股6位数字: ^[0-9]{6}$ -> c_symbol = CN:stock:<raw>
- CN 基金: ^(\d{6})$ 且 asset_type=fund -> c_symbol = CN:fund:<raw>
- 指数(示例: 000300 -> 沪深300) pattern: ^0003\d{2}$ -> c_symbol=CN:index:<raw>

Algorithm (normalize)
1 Check cache -> return if hit
2 Iterate rules (priority asc):
   if rule applicable(market/asset) and match(pattern): core=transform(raw)
   compose c_symbol = market.upper() + ":" + asset_type + ":" + core
   update counters & cache -> return
3 If no rule matched → raise UnresolvedSymbolError(detail={raw,market,asset_type})

Phase 2 起将追加 normalize 成功后的 symbol_map 持久化逻辑。

Batch Algorithm (normalize_batch, Phase 2+)
for each raw: try normalize; collect {raw, status=ok|error, c_symbol|error_reason}
return BatchResult(successes, failures, stats)

Caching Strategy
- LRU(key=(raw,market,asset_type), value=CanonicalSymbol)
- Max size configurable (default 10k); eviction increments eviction_counter

Error Model
UnresolvedSymbolError(code=SYMBOL_UNRESOLVED, retryable=false)
RuleConflictError(code=SYMBOL_RULE_CONFLICT) (Should, 若同优先级重复匹配检测)

Testing Strategy
- Parametrized tests: stock/fund/index 命中规则
- 未命中返回结构化错误
- 缓存命中统计正确性 (首次miss,二次hit)
- 规则优先级覆盖 (高优先级抢占)
- 批量部分成功场景 (Phase 2+)
- 规则热更新后新规则生效 (Phase 2+)

Open Questions
- 实际指数/基金前缀/后缀细节待补: 需要真实 mapping 样本
- 是否需要 exchange 维度 (SSE/SZSE) 进 canonical 结构 (Could)
- 是否需要大小写不敏感统一 (假设统一 upper for market, lower for core)
- 是否支持正则捕获组直接引用 transform 中 group (Yes, 计划内)

Risks & Mitigations
- 规则扩散难维护 → 后续引入外部配置文件 + 校验工具
- 模糊匹配噪音 → 默认关闭，需显式 flag
- 未来多市场冲突 → canonical 前缀包含 market 避免冲突

Acceptance Criteria
- normalize 对示例规则全通过 & 覆盖率≥85%
- 未命中符号抛 UnresolvedSymbolError 且包含 diagnostics(raw,market,asset_type)
- metrics.hit_rate 在二次调用测试 ≥50%(因二次缓存)
- 无持久化写入，所有状态留在内存 (确认无 DuckDB 依赖)

Rollout Plan
Phase 1: 内存版 SymbolService（内置规则 + LRU 缓存 + 命中统计，无批量/持久化）
Phase 2: 引入 normalize_batch 与 DuckDB symbol_map 持久化 + 统计导出
Phase 3: 引入 reload + 外部配置文件 + 可选模糊建议 & provider capability 感知

Future Extensions
- Exchange 级别细分 (CN:SZ / CN:SH)
- 历史重命名 alias 表
- 退市标记字段 retired_flag
- Multi-source cross-verification (对账辅助)

Implementation Notes
- 放置于 vprism/core/services/symbols.py (示例目录, 若存在冲突需对齐现有结构)
- 提供 SymbolService + Rule dataclass + NormalizationResult model
- 避免在 provider adapter 内直接写规则

Next Steps
1 确认真实映射样本 (Blocking)
2 实现 Rule + Service + 缓存
3 编写测试 & 接入 ingestion 前测试钩子
