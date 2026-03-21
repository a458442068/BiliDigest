## ADDED Requirements

### Requirement: STT 后端配置
系统SHALL支持通过配置选择 STT 后端模式。

#### Scenario: 配置 STT 后端
- **WHEN** 设置 STT_BACKEND 环境变量为 "default"
- **THEN** 系统优先使用本地模型，失败时 fallback 到远程服务

#### Scenario: 配置本地模式
- **WHEN** 设置 STT_BACKEND 环境变量为 "local"
- **THEN** 系统仅使用本地模型，不 fallback

#### Scenario: 配置远程模式
- **WHEN** 设置 STT_BACKEND 环境变量为 "remote"
- **THEN** 系统仅使用远程 STT 服务，不 fallback

### Requirement: 远程 STT 调用
系统SHALL支持调用 OpenAI-compatible STT API。

#### Scenario: 远程转录
- **WHEN** STT 后端为远程或 fallback 到远程
- **THEN** 系统调用 STT_API_URL/v1/audio/transcriptions 接口

#### Scenario: 使用默认模型
- **WHEN** 调用远程 STT API
- **THEN** 系统不指定 model 参数，使用远程服务默认模型

#### Scenario: 响应解析
- **WHEN** 远程 STT API 返回 verbose_json 格式
- **THEN** 系统解析 text、language、duration 字段

### Requirement: Fallback 机制
系统SHALL在 default 模式下支持本地到远程的 fallback。

#### Scenario: 本地成功
- **WHEN** 本地 STT 推理成功
- **THEN** 系统返回本地结果，不调用远程

#### Scenario: 本地失败，远程成功
- **WHEN** 本地 STT 推理失败且后端为 default
- **THEN** 系统自动调用远程 STT，返回远程结果

#### Scenario: 双端失败
- **WHEN** 本地和远程 STT 都失败
- **THEN** 系统返回包含两个错误信息的 STTError

### Requirement: 错误信息
系统SHALL在双端失败时返回明确的错误信息。

#### Scenario: 记录本地错误
- **WHEN** 本地 STT 失败
- **THEN** 系统记录本地错误原因到日志

#### Scenario: 记录远程错误
- **WHEN** 远程 STT 失败
- **THEN** 系统记录远程错误原因到日志

#### Scenario: 返回综合错误
- **WHEN** 双端都失败
- **THEN** 系统返回 STTError，消息包含本地和远程各自的错误信息
