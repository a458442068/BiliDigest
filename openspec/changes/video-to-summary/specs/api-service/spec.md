## ADDED Requirements

### Requirement: 提供视频处理API
系统SHALL提供RESTful API接口用于处理视频。

#### Scenario: 提交处理任务
- **WHEN** 客户端POST /api/v1/process并提供url参数
- **THEN** 系统处理视频并返回结果

#### Scenario: 请求格式错误
- **WHEN** 客户端提交的请求格式错误
- **THEN** 系统返回400状态码和错误信息

### Requirement: 支持处理选项
系统SHALL支持通过options参数控制处理流程。

#### Scenario: 启用翻译
- **WHEN** 客户端设置options.translate为true
- **THEN** 系统对英文内容进行翻译

#### Scenario: 启用摘要
- **WHEN** 客户端设置options.summarize为true
- **THEN** 系统生成内容摘要

#### Scenario: 默认不启用翻译和摘要
- **WHEN** 客户端未设置options或translate/summarize为false
- **THEN** 系统仅执行下载和STT

### Requirement: 返回统一响应格式
系统SHALL返回统一的JSON响应格式。

#### Scenario: 成功响应
- **WHEN** 处理成功
- **THEN** 系统返回status为"success"的响应，包含data字段

#### Scenario: 错误响应
- **WHEN** 处理失败
- **THEN** 系统返回status为"error"的响应，包含error字段

### Requirement: 错误信息详细
系统SHALL返回详细的错误信息。

#### Scenario: 下载错误
- **WHEN** 下载阶段失败
- **THEN** 系统返回error.stage为"download"，包含错误码和消息

#### Scenario: STT错误
- **WHEN** STT阶段失败
- **THEN** 系统返回error.stage为"stt"，包含错误码和消息

#### Scenario: 翻译错误
- **WHEN** 翻译阶段失败
- **THEN** 系统返回error.stage为"translation"，包含错误码和消息

#### Scenario: 摘要错误
- **WHEN** 摘要阶段失败
- **THEN** 系统返回error.stage为"summarization"，包含错误码和消息

### Requirement: 提供健康检查接口
系统SHALL提供健康检查接口。

#### Scenario: 健康检查
- **WHEN** 客户端GET /api/v1/health
- **THEN** 系统返回服务状态信息

### Requirement: 支持配置
系统SHALL支持通过环境变量进行配置。

#### Scenario: 配置B站cookie
- **WHEN** 设置BILIBILI_COOKIE环境变量
- **THEN** 系统使用该cookie下载需要登录的视频

#### Scenario: 配置LLM后端
- **WHEN** 设置LLM_PROVIDER环境变量
- **THEN** 系统使用指定的LLM后端进行翻译和摘要

#### Scenario: 配置STT模型路径
- **WHEN** 设置QWEN_ASR_MODEL_PATH环境变量
- **THEN** 系统使用指定的模型路径

#### Scenario: 配置服务端口
- **WHEN** 设置PORT环境变量
- **THEN** 系统在指定端口启动服务

### Requirement: 串行处理
系统SHALL串行处理任务，不支持并发。

#### Scenario: 单任务处理
- **WHEN** 收到处理请求
- **THEN** 系统串行执行下载、STT、翻译、摘要步骤

#### Scenario: 并发请求
- **WHEN** 同时收到多个处理请求
- **THEN** 系统按顺序处理，后续请求等待
