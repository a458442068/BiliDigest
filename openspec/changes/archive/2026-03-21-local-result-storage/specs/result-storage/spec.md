## ADDED Requirements

### Requirement: 结果目录配置
系统SHALL支持通过环境变量配置结果保存目录。

#### Scenario: 配置结果目录
- **WHEN** 设置 RESULT_DIR 环境变量
- **THEN** 系统将处理结果保存到该目录下

#### Scenario: 默认结果目录
- **WHEN** 未设置 RESULT_DIR 环境变量
- **THEN** 系统使用 `./results` 作为默认结果目录

### Requirement: 按BV号保存结果
系统SHALL按BV号创建子目录保存结果。

#### Scenario: 单P视频
- **WHEN** 处理单P视频 BV1GJ411x7h7
- **THEN** 系统创建 `{RESULT_DIR}/BV1GJ411x7h7/` 目录

#### Scenario: 多P视频
- **WHEN** 处理多P视频 BV1GJ411x7h7（含3个分P）
- **THEN** 系统创建 `{RESULT_DIR}/BV1GJ411x7h7/` 目录

### Requirement: 每步落盘
系统SHALL在每步处理完成后立即保存结果到本地目录。

#### Scenario: 下载完成后保存音频
- **WHEN** 下载完成
- **THEN** 系统将音频文件复制到 `{RESULT_DIR}/{BV}/audio.wav`（单P）或 `{RESULT_DIR}/{BV}/P{n}_audio.wav`（多P）

#### Scenario: STT完成后保存文字稿
- **WHEN** 语音识别完成
- **THEN** 系统将文字稿保存到 `{RESULT_DIR}/{BV}/transcript.txt`（单P）或 `{RESULT_DIR}/{BV}/P{n}_transcript.txt`（多P）

#### Scenario: 翻译完成后保存翻译
- **WHEN** 翻译完成
- **THEN** 系统将翻译结果保存到 `{RESULT_DIR}/{BV}/translation.txt`（单P）或 `{RESULT_DIR}/{BV}/P{n}_translation.txt`（多P）

#### Scenario: 摘要完成后保存摘要
- **WHEN** 摘要生成完成
- **THEN** 系统将摘要保存到 `{RESULT_DIR}/{BV}/summary.txt`（单P）或 `{RESULT_DIR}/{BV}/P{n}_summary.txt`（多P）

### Requirement: metadata.json
系统SHALL维护 metadata.json 记录处理信息。

#### Scenario: 记录基本信息
- **WHEN** 开始处理视频
- **THEN** 系统创建 metadata.json 记录 url、bv_id、created_at

#### Scenario: 记录模型信息
- **WHEN** 完成处理
- **THEN** 系统在 metadata.json 中记录 stt_model、llm_model

#### Scenario: 记录分P信息
- **WHEN** 处理多P视频
- **THEN** 系统在 metadata.json 的 parts 数组中记录每个分P的 language、duration_seconds、has_* 状态

### Requirement: 保留部分结果
系统SHALL在处理失败时保留已保存的结果。

#### Scenario: 下载成功STT失败
- **WHEN** 下载成功但STT失败
- **THEN** 系统保留已保存的 audio.wav，不删除

#### Scenario: 重试从失败点继续
- **WHEN** 用户重新请求同一视频
- **THEN** 系统检查已有结果，从失败点继续处理

## ADDED Requirements (cache-resume)

### Requirement: 缓存检查
系统SHALL在每步执行前检查本地是否已有结果。

#### Scenario: 缓存命中
- **WHEN** 本地已有该步骤的结果文件
- **THEN** 系统跳过该步骤，使用缓存结果

#### Scenario: 缓存未命中
- **WHEN** 本地没有该步骤的结果文件
- **THEN** 系统执行该步骤并保存结果

### Requirement: 配置变化检测
系统SHALL检测STT模型和LLM配置是否变化。

#### Scenario: STT模型变化
- **WHEN** metadata 中的 stt_model 与当前配置不同
- **THEN** 系统重命名旧 transcript 文件，重新执行STT

#### Scenario: LLM模型变化
- **WHEN** metadata 中的 llm_model 与当前配置不同
- **THEN** 系统重命名旧 translation 和 summary 文件，重新执行翻译和摘要

#### Scenario: 配置未变化
- **WHEN** metadata 中的模型与当前配置一致
- **THEN** 系统使用缓存结果

### Requirement: 强制重跑
系统SHALL支持通过API参数强制重新处理。

#### Scenario: 强制重跑
- **WHEN** 客户端设置 options.force 为 true
- **THEN** 系统忽略所有缓存，重新执行所有步骤

#### Scenario: 不强制
- **WHEN** 客户端未设置 force 或 force 为 false
- **THEN** 系统优先使用缓存结果

## ADDED Requirements (api-service)

### Requirement: force 参数
系统SHALL支持通过 options.force 参数控制是否强制重跑。

#### Scenario: 强制重跑请求
- **WHEN** 客户端 POST /api/v1/process 并设置 options.force 为 true
- **THEN** 系统忽略缓存，重新处理

#### Scenario: 默认使用缓存
- **WHEN** 客户端未设置 options.force
- **THEN** 系统默认使用缓存（force = false）

### Requirement: 返回结果目录和缓存信息
系统SHALL在响应中返回结果目录和缓存命中信息。

#### Scenario: 返回结果目录
- **WHEN** 处理成功
- **THEN** 系统返回 result_dir 字段

#### Scenario: 返回缓存命中步骤
- **WHEN** 部分步骤使用了缓存
- **THEN** 系统返回 cached_steps 列表
