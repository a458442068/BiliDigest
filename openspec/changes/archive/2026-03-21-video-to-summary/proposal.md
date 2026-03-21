## Why

用户需要一个自动化工具来理解视频内容，能够从B站视频链接（BV号或URL）中提取音频，转换为文字稿，并支持英文翻译为中文，最后生成摘要。这解决了手动转录和理解视频内容的低效问题，特别适用于需要快速获取视频核心信息的场景。

## What Changes

- 新建一个完整的视频理解服务，支持从B站视频到文字摘要的全流程处理
- 实现B站音频下载功能，支持BV号和完整URL输入
- 集成本地STT模型（Qwen3-ASR-1.7B）进行语音识别
- 提供翻译功能，将英文内容翻译为中文
- 提供摘要生成功能，基于文字稿生成内容摘要
- 搭建FastAPI HTTP服务，向本地其他服务器提供能力
- 完善的错误处理机制，任何环节失败都返回明确的错误信息
- 使用Git进行版本控制，每个功能实现后提交代码，保持清晰的提交历史

## Capabilities

### New Capabilities
- `bilibili-downloader`: 从B站视频链接下载音频文件，支持BV号和完整URL
- `speech-to-text`: 使用Qwen3-ASR-1.7B模型将音频转换为文字，支持多语言识别
- `translation`: 将英文文字稿翻译为中文，支持多种LLM后端
- `summarization`: 基于文字稿生成内容摘要，支持多种LLM后端
- `api-service`: 提供RESTful API服务，支持视频处理任务的提交和结果获取

### Modified Capabilities
（无，这是全新项目）

## Impact

- **依赖**: 需要安装 yt-dlp、qwen_asr、fastapi、uvicorn、pydantic、loguru 等Python包
- **硬件**: 需要GPU支持（RTX 2060 Max-Q 6GB），用于运行Qwen3-ASR-1.7B模型
- **存储**: 需要下载Qwen3-ASR-1.7B模型文件（约3.5GB）
- **网络**: 需要网络访问以下载B站视频和可能的LLM API调用
- **系统**: 需要ffmpeg支持音频格式转换
