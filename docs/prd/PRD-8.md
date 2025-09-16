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
Should:
- 自动多次连续 PASS (>=N 次) 才允许 promote
- CLI: shadow run / shadow status / shadow promote / shadow diff show
Could:
- 按 symbol 分类差异热力列表
- 历史趋势 sparkline
Out of Scope:
- 自动自适应调参

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
