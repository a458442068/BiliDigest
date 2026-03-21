## Why

当前视频处理结果（音频、文字稿、翻译、摘要）在处理完成后被删除，无法复用。用户需要：
1. 保留处理结果以便后续查看和使用
2. 避免重复处理已完成的步骤（节省时间和计算资源）
3. 在配置变更时（换模型、换LLM）自动感知并重跑受影响的步骤

## What Changes

- 添加本地结果存储功能，每步处理完成后立即落盘
- 实现缓存机制，优先使用已有结果，避免重复计算
- 支持配置变化检测，模型变更时自动重命名旧文件并重跑
- 支持B站多分P视频，每个分P独立保存结果
- 添加 `force` 参数支持强制重跑
- 添加 `RESULT_DIR` 配置项指定存储目录

## Capabilities

### New Capabilities
- `result-storage`: 本地结果存储，按BV号分子目录，每步落盘
- `cache-resume`: 缓存断点续跑，优先使用已有结果
- `config-change-detection`: 配置变化检测，模型变更时自动重跑
- `multi-part-support`: B站多分P视频支持

### Modified Capabilities
- `bilibili-downloader`: 移除 `--no-playlist`，支持多分P下载
- `api-service`: `ProcessOptions` 添加 `force` 字段，`ProcessResult` 添加 `result_dir`、`cached_steps`
- `pipeline`: 重写为 step-by-step 缓存检查 + 落盘

## Impact

- **存储**: 需要磁盘空间存储结果（音频 + 文本），可通过 `RESULT_DIR` 配置
- **性能**: 缓存命中时几乎瞬时返回，无需重新计算
- **兼容性**: 现有 API 接口不变，仅扩展字段
