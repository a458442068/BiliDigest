## Why

当前 STT 服务仅支持本地 Qwen3-ASR 模型推理。在以下场景中存在限制：
1. 本地 GPU 显存不足时无法处理
2. 模型未加载或加载失败时服务不可用
3. 没有 fallback 机制，单一后端故障即整体失败

需要支持远程 STT 服务作为备选方案，提供更可靠的服务。

## What Changes

- 新增 `stt_backend` 配置项，支持 `default` / `local` / `remote` 三种模式
- `default` 模式：优先本地推理，失败时自动 fallback 到远程服务
- `remote` 模式：仅使用远程 OpenAI-compatible STT API
- `local` 模式：仅使用本地模型，不 fallback
- 新增 `stt_api_url` 和 `stt_api_key` 配置远程服务
- 双端失败时返回明确的错误信息，不重试

## Capabilities

### Modified Capabilities
- `speech-to-text`: 扩展支持远程 STT 后端和 fallback 机制

## Impact

- **配置**: 新增 3 个环境变量
- **兼容性**: 默认 `default` 模式对现有行为无影响（本地优先）
- **依赖**: 远程模式需要网络访问 STT 服务
