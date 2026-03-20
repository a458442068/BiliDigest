## ADDED Requirements

### Requirement: 使用Qwen3-ASR-1.7B进行语音识别
系统SHALL使用Qwen3-ASR-1.7B模型将音频转换为文字。

#### Scenario: 识别中文音频
- **WHEN** 输入音频为中文内容
- **THEN** 系统返回中文文字稿，language字段为"zh"

#### Scenario: 识别英文音频
- **WHEN** 输入音频为英文内容
- **THEN** 系统返回英文文字稿，language字段为"en"

#### Scenario: 识别多语言音频
- **WHEN** 输入音频包含多种语言
- **THEN** 系统识别主要语言并返回对应文字稿

### Requirement: 支持多种音频格式
系统SHALL支持常见的音频格式输入，并自动处理格式转换。

#### Scenario: WAV格式（16kHz单声道）
- **WHEN** 输入音频为WAV格式且采样率为16kHz单声道
- **THEN** 系统正常处理并返回文字稿

#### Scenario: MP3格式
- **WHEN** 输入音频为MP3格式
- **THEN** 系统正常处理并返回文字稿

#### Scenario: FLAC格式
- **WHEN** 输入音频为FLAC格式
- **THEN** 系统正常处理并返回文字稿

#### Scenario: M4A格式
- **WHEN** 输入音频为M4A格式
- **THEN** 系统正常处理并返回文字稿

#### Scenario: 不支持的格式，转换成功
- **WHEN** 输入音频格式不被STT支持
- **THEN** 系统使用ffmpeg转换为WAV格式（16kHz单声道），然后进行语音识别

#### Scenario: 不支持的格式，转换失败
- **WHEN** 输入音频格式不被STT支持且ffmpeg转换失败
- **THEN** 系统返回STTError，错误码为FORMAT_CONVERSION_ERROR

#### Scenario: 采样率不正确，自动重采样
- **WHEN** 输入音频采样率不是16kHz
- **THEN** 系统自动重采样到16kHz单声道，然后进行语音识别

### Requirement: 返回语言检测结果
系统SHALL检测音频的主要语言并返回。

#### Scenario: 检测中文
- **WHEN** 音频主要为中文
- **THEN** 系统返回language为"zh"

#### Scenario: 检测英文
- **WHEN** 音频主要为英文
- **THEN** 系统返回language为"en"

### Requirement: GPU显存管理
系统SHALL正确管理GPU显存。

#### Scenario: 显存充足
- **WHEN** GPU显存足够加载模型
- **THEN** 系统正常加载模型并进行推理

#### Scenario: 显存不足
- **WHEN** GPU显存不足以加载模型
- **THEN** 系统返回STTError，错误码为OUT_OF_MEMORY

### Requirement: 模型加载错误处理
系统SHALL正确处理模型加载相关错误。

#### Scenario: 模型文件不存在
- **WHEN** Qwen3-ASR-1.7B模型文件未下载或路径错误
- **THEN** 系统返回STTError，错误码为MODEL_LOAD_ERROR

#### Scenario: 模型加载失败
- **WHEN** 模型加载过程中出现错误
- **THEN** 系统返回STTError，错误码为MODEL_LOAD_ERROR

### Requirement: 推理错误处理
系统SHALL正确处理推理过程中的错误。

#### Scenario: 推理异常
- **WHEN** 推理过程中出现未知错误
- **THEN** 系统返回STTError，错误码为INFERENCE_ERROR

### Requirement: 返回音频时长
系统SHALL返回音频的时长信息。

#### Scenario: 获取时长
- **WHEN** 成功完成语音识别
- **THEN** 系统返回duration_seconds字段，包含音频时长（秒）
