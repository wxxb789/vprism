PRD-9 漂移统计与插件框架 (Data Drift & Plugin Framework)

Goal
: 监测关键统计漂移，提供轻量插件机制加速功能扩展。

Scope
Must (Drift):
- DriftService.compute(symbol, market, window=30) -> DriftResult
- 指标: close_mean, close_std, volume_mean, volume_std, zscore_latest_close, zscore_latest_volume
- 阈值: |zscore| warn>=2 fail>=3
- drift_metrics 表(date,market,symbol,metric,value,status,window,run_id,created_at)
Must (Plugin):
- 插件入口点 group: vprism.plugins
- Plugin 接口: register(cli_app, services_registry)
- 自动发现并注册非冲突命令
- 冲突策略: 后加载跳过并警告
Should:
- CLI: drift report --symbol 000001 --market cn --window 30
- 配置可调整窗口与阈值
Could:
- EWMA 替代均值; 波动率年化
- 插件生命周期 hooks (init/teardown)
Out of Scope:
- 复杂 ML 异常检测
- Auto-remediation

Algorithm (Drift)
1 取最近 window+1 天 normalized close/volume
2 计算 mean/std (样本标准差)
3 最新值 z = (x_last - mean)/std
4 分类状态: OK/WARN/FAIL
5 写 drift_metrics 行

Testing Strategy
- 正常波动 -> OK
- 人造尖峰 close_last=mean+3*std -> FAIL
- 人造中度偏移 +2*std -> WARN
- std=0 边界处理 (全部相同) => zscore=0
- 插件加载: 注入模拟插件生成新命令
- 冲突命令检测

Open Questions
- 是否对 volume 使用 log 变换 (初期否)
- 是否需要对缺口天数填补 (初期直接跳过不足 window)

Data Model (DuckDB)
drift_metrics:
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

Acceptance Criteria
- 漂移状态分类符合阈值
- 插件可注册并出现在 --help 列表
- 冲突命令记录警告不抛异常
- 覆盖率≥75%

Risks & Mitigations
- 假阳性报警 → 使用 WARN/FAIL 双阈值
- 高基数写入 → 限制符号级漂移仅按采样
- 插件破坏兼容 → 提供接口版本号

Rollout Plan
Phase 1: 基础 zscore 漂移 + CLI
Phase 2: 插件发现 + 冲突处理
Phase 3: 扩展指标(EWMA/波动率) & 配置化

Next Steps
1 DriftService 实现
2 写入 drift_metrics 表
3 CLI drift report
4 插件加载器与测试
