PRD-9 漂移统计与插件框架 (Data Drift & Plugin Framework)

## 概览 (Overview)
本 PRD 拆分为两个顺序执行的阶段：
1. **Phase 1 — 漂移统计基线 (Drift Metrics Baseline)**：建立可审计的 z-score 漂移监测能力与 CLI 报表。
2. **Phase 2 — 插件加载框架 (Plugin Loader Framework)**：基于 Phase 1 的服务注册机制，提供自动发现与冲突管理的插件系统。

## Phase 1 — 漂移统计基线
### Goal
: 监测关键行情指标的统计漂移，并输出结构化结果以支撑后续扩展。

### Scope
#### Must
- DriftService.compute(symbol, market, window=30) -> DriftResult
- 指标: close_mean, close_std, volume_mean, volume_std, zscore_latest_close, zscore_latest_volume
- 阈值: \|zscore\| warn>=2 fail>=3
- `drift_metrics` 表(date, market, symbol, metric, value, status, window, run_id, created_at)
#### Should
- CLI: `drift report --symbol 000001 --market cn --window 30`
- 配置可调整窗口与阈值
#### Could
- EWMA 替代均值; 波动率年化
#### Out of Scope
- 复杂 ML 异常检测
- Auto-remediation

### Algorithm
1. 取最近 window+1 天 normalized close/volume
2. 计算 mean/std (样本标准差)
3. 最新值 z = (x_last - mean)/std
4. 分类状态: OK/WARN/FAIL
5. 写入 `drift_metrics` 行

### Testing Strategy
- 正常波动 -> OK
- 人造尖峰 close_last=mean+3*std -> FAIL
- 人造中度偏移 +2*std -> WARN
- std=0 边界处理 (全部相同) => zscore=0

### Open Questions
- 是否对 volume 使用 log 变换 (初期否)
- 是否需要对缺口天数填补 (初期直接跳过不足 window)

### Data Model (DuckDB)
`drift_metrics`:
  date DATE
  market TEXT
  symbol TEXT
  metric TEXT
  value DOUBLE
  status TEXT
  window INT
  run_id TEXT
  created_at TIMESTAMP
  PRIMARY KEY(date,market,symbol,metric,window,run_id)

### Acceptance Criteria
- 漂移状态分类符合阈值
- CLI 报表可展示并导出上述指标
- 覆盖率≥75%

### Risks & Mitigations
- 假阳性报警 → 使用 WARN/FAIL 双阈值
- 高基数写入 → 限制符号级漂移仅按采样

### Rollout Plan
1. 完成 DriftService 核心计算与单元测试
2. 建表迁移与批量写入流程
3. CLI 报表与配置参数下发

### Next Steps
1. DriftService 实现
2. 写入 `drift_metrics` 表
3. CLI `drift report`

## Phase 2 — 插件加载框架
### Goal
: 构建可扩展的插件发现与注册机制，使外部模块能够安全扩展 CLI 与服务。

### Scope
#### Must
- 插件入口点 group: `vprism.plugins`
- 插件接口: `register(cli_app, services_registry)`
- 自动发现并注册非冲突命令
- 冲突策略: 后加载跳过并警告
#### Should
- 插件注册支持依赖检测与最小日志
#### Could
- 插件生命周期 hooks (init/teardown)
#### Out of Scope
- 插件沙箱隔离与权限控制（后续版本处理）

### Integration Dependencies
- 依赖 Phase 1 暴露的 DriftService 与指标注册能力
- 需与 CLI 配置系统对齐参数注入方式

### Testing Strategy
- 插件加载: 注入模拟插件生成新命令
- 冲突命令检测与警告校验

### Acceptance Criteria
- 插件可注册并出现在 `--help` 列表
- 冲突命令记录警告不抛异常
- 插件注册日志可追踪加载顺序

### Risks & Mitigations
- 插件破坏兼容 → 提供接口版本号并在加载时校验
- 外部插件质量不稳 → 提供隔离环境和禁用开关

### Rollout Plan
1. 定义插件接口与入口点，并更新文档
2. 实现自动发现与注册流程（含冲突检测）
3. 编写示例插件与端到端测试

### Next Steps
1. 插件加载器实现与测试
2. 文档化插件接口
3. 准备示例插件仓库
