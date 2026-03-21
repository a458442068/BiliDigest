## Context

当前 STT 服务仅支持本地 Qwen3-ASR 模型。需要扩展支持远程 OpenAI-compatible STT 服务作为备选，提供 fallback 机制提高可靠性。

## Goals / Non-Goals

**Goals:**
- 支持本地/远程/默认三种 STT 后端模式
- 默认模式下本地优先，失败自动 fallback
- 双端失败返回明确错误信息
- 远程调用使用默认模型，不指定模型名
- 超时时间足够长（600秒），避免长语音中断

**Non-Goals:**
- 不实现自动重试逻辑
- 不实现负载均衡或多个远程服务
- 不实现 STT 结果质量对比选择

## Decisions

### 1. 后端模式
**选择**: `stt_backend` 配置项，三个值

- `default`: 本地优先，失败 fallback 远程
- `local`: 仅本地，不 fallback
- `remote`: 仅远程，不 fallback

**理由**: 灵活配置，满足不同场景需求

### 2. 远程 API 调用
**选择**: 使用 `httpx` 调用 OpenAI-compatible API

**端点**: `POST /v1/audio/transcriptions`
**参数**:
- `file`: 音频文件
- `response_format`: `verbose_json`
- 不指定 `model`，使用远程服务默认模型

**理由**: 兼容 OpenAI Whisper API 格式

### 3. 错误处理
**选择**: 双端失败不重试，返回包含两个错误信息的 STTError

**日志**: 记录每个后端失败的具体原因
**响应**: 包含本地和远程各自的错误信息

**理由**: 简单可靠，便于调试

### 4. 超时设置
**选择**: 远程调用超时 600 秒

**理由**: 长音频处理可能需要较长时间

## Risks

### 风险1: 远程服务不可用
**影响**: fallback 也失败
**缓解措施**: 返回明确错误信息

### 风险2: 远程服务响应格式变化
**影响**: 解析失败
**缓解措施**: 健壮的响应解析，使用 `.get()` 安全访问
