PRD-8 影子管线与切换 (Shadow Pipeline & Cutover)

Goal
: 通过影子(Shadow) 双路径运行与差异度量，实现无停机平滑迁移。

Scope
Must:
- ShadowController: duplicate(query)-> old_path_result + new_path_result (new 不返回用户)
- DiffEngine: compare(row_count, price_diff_bp, gap_ratio)
- 阈值判定: pass if row_diff<=1%, price_diff_bp_p95<=5, gap_ratio<=0.5%
- 统计写 shadow_runs(run_id,start,end,asset,markets,created_at, row_diff_pct, price_diff_bp_p95, gap_ratio, status)
- Promote 逻辑: 手动触发 promote() 切换 flag
- 回滚: flag revert 即恢复旧路径
- 影子运行默认按采样执行，基于 symbol 哈希选择 25% 高流动性标的，日更轮转一周全覆盖
Should:
- 自动多次连续 PASS (>=N 次) 才允许 promote
- CLI: shadow run / shadow status / shadow promote / shadow diff show
Could:
- 按 symbol 分类差异热力列表
- 历史趋势 sparkline
Out of Scope:
- 自动自适应调参

- Rolling 时间窗口采样: 默认 shadow run 仅拉取最近 30 天交易日数据，支持按需扩展

Configuration & Controls
- `shadow.sample.mode`: `symbols` / `date_range` / `full`，决定采样维度，默认 `symbols`
- `shadow.sample.percent`: 0-100 的百分比，控制 symbol 采样比例，默认 25%，上限保护 50%
- `shadow.sample.lookback_days`: 控制日期窗口大小，默认 30 天，0=不限制
- `shadow.sample.max_rows`: 限制总行数上限 (如 5M) 防止资源爆炸，命中后自动降采样
- `shadow.force_full_run`: 布尔开关，临时强制跑全量用于最终验证
- 配置来源支持 env/CLI 覆盖，CLI 优先级最高

Algorithm
1 接收用户查询 -> 正常走旧路径(response 给用户)
2 并行异步执行新路径 -> 收集 normalized+adjusted 输出
3 对齐主键(symbol,date) 进行行差/价格差/缺口计算
4 更新 shadow_runs 表 & 追加明细 (可选)
5 若连续 N 次 PASS, 标记 ready_for_promote

Testing Strategy
- 人造价格偏移 10bp -> FAIL
- 行数缺失 2% -> FAIL
- 连续 PASS N 次后 promote 允许
- 回滚后仅旧路径执行
- 采样模式下仅执行采样子集，验证 shadow_runs 记录采样比例/窗口
- 配置 `shadow.force_full_run=true` 跑全量，确认阈值逻辑一致且资源预算可接受

Open Questions
- N 次 PASS 默认值 (假设3)
- 是否需要明细表 (初期不写, 只聚合)
- 是否对差异进行分桶 (后续 Could)

Acceptance Criteria
- 阈值条件满足 status=PASS, 违反=FAIL
- promote 切换后查询仅走新路径
- 回滚立即生效
- 覆盖率≥70%

Risks & Mitigations
- 双路径性能开销 → 限制并发 + 仅样本子集 shadow
- 差异噪音 (复权模式) → 使用 raw close 对比
- 动态负载变化 → 提供关闭 shadow flag

Rollout Plan
Phase 1: 基础双写+聚合 diff
Phase 2: 多次 PASS 门槛与 CLI
Phase 3: 明细与可视化扩展

Next Steps
1 ShadowController 框架
2 DiffEngine 实现
3 CLI commands
4 测试门槛 & promote/rollback
