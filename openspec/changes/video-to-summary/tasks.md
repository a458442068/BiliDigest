## 1. 项目初始化

- [x] 1.1 使用uv初始化项目
- [x] 1.2 创建pyproject.toml，添加基础依赖（yt-dlp, fastapi, uvicorn, pydantic, pydantic-settings, loguru, httpx）
- [x] 1.3 创建项目目录结构（src/, src/api/, src/services/, src/models/, src/utils/, tests/）
- [x] 1.4 创建.env.example配置文件示例
- [ ] 1.5 初始化Git仓库，提交初始代码（commit: `chore: 初始化项目结构和基础依赖`）

## 2. 基础设施

- [ ] 2.1 实现config.py，使用pydantic-settings管理环境变量配置
- [ ] 2.2 实现exceptions.py，定义统一异常类（DownloadError, STTError, TranslationError, SummarizationError, ProcessError）
- [ ] 2.3 实现logger.py，配置loguru日志
- [ ] 2.4 实现schemas.py，定义请求和响应的Pydantic模型（ProcessRequest, ProcessResult, ErrorResponse）
- [ ] 2.5 提交基础设施代码（commit: `feat: 实现配置管理、异常定义和日志系统`）

## 3. B站下载服务

- [ ] 3.1 实现downloader.py中的BilibiliDownloader类
- [ ] 3.2 实现BV号和URL解析逻辑
- [ ] 3.3 配置yt-dlp仅下载音频流，输出wav格式
- [ ] 3.4 实现错误处理（网络错误、视频不存在、需要登录）
- [ ] 3.5 创建test_downloader.py测试下载功能
- [ ] 3.6 提交下载服务代码（commit: `feat: 实现B站音频下载功能`）

## 4. STT服务

- [ ] 4.1 添加qwen_asr, soundfile, torch依赖到pyproject.toml
- [ ] 4.2 实现stt.py中的SpeechToText类
- [ ] 4.3 实现模型加载逻辑（Qwen3-ASR-1.7B）
- [ ] 4.4 实现音频转文字功能
- [ ] 4.5 实现语言检测和返回
- [ ] 4.6 实现GPU显存管理和错误处理
- [ ] 4.7 创建test_stt.py测试STT功能
- [ ] 4.8 提交STT服务代码（commit: `feat: 集成Qwen3-ASR语音识别模型`）

## 5. 流水线编排

- [ ] 5.1 实现pipeline.py中的ProcessingPipeline类
- [ ] 5.2 实现下载→STT的基本流程
- [ ] 5.3 实现错误捕获和统一错误响应
- [ ] 5.4 实现临时文件清理
- [ ] 5.5 提交流水线代码（commit: `feat: 实现处理流水线编排`）

## 6. API服务

- [ ] 6.1 实现routes.py中的API路由
- [ ] 6.2 实现POST /api/v1/process端点
- [ ] 6.3 实现GET /api/v1/health端点
- [ ] 6.4 实现main.py，配置FastAPI应用
- [ ] 6.5 实现请求验证和错误响应
- [ ] 6.6 添加CORS配置（如需要）
- [ ] 6.7 提交API服务代码（commit: `feat: 搭建FastAPI HTTP服务`）

## 7. 翻译服务（占位）

- [ ] 7.1 实现translator.py中的Translator类
- [ ] 7.2 实现语言检测，非英文直接返回原文
- [ ] 7.3 实现LLM后端接口（占位，抛出NotImplementedError）
- [ ] 7.4 集成到pipeline中作为可选步骤
- [ ] 7.5 提交翻译服务代码（commit: `feat: 实现翻译服务框架（占位）`）

## 8. 摘要服务（占位）

- [ ] 8.1 实现summarizer.py中的Summarizer类
- [ ] 8.2 实现LLM后端接口（占位，抛出NotImplementedError）
- [ ] 8.3 集成到pipeline中作为可选步骤
- [ ] 8.4 提交摘要服务代码（commit: `feat: 实现摘要服务框架（占位）`）

## 9. 集成测试

- [ ] 9.1 测试完整的下载→STT流程
- [ ] 9.2 测试API端点的正确响应
- [ ] 9.3 测试各种错误场景的处理
- [ ] 9.4 测试配置文件的正确加载
- [ ] 9.5 提交测试代码（commit: `test: 添加集成测试`）

## 10. 文档和部署

- [ ] 10.1 编写README.md，说明安装和使用方法
- [ ] 10.2 编写API文档
- [ ] 10.3 测试服务启动和运行
- [ ] 10.4 优化性能和资源使用
- [ ] 10.5 提交文档（commit: `docs: 添加项目文档和使用说明`）

## 11. 音频格式处理

- [ ] 11.1 添加ffmpeg依赖检查功能
- [ ] 11.2 实现音频格式检测函数（使用soundfile或librosa）
- [ ] 11.3 实现采样率检测函数
- [ ] 11.4 实现ffmpeg格式转换函数（输出WAV 16kHz单声道）
- [ ] 11.5 实现采样率自动重采样功能
- [ ] 11.6 集成到downloader.py（下载后检查和转换）
- [ ] 11.7 集成到stt.py（推理前检查和转换作为兜底）
- [ ] 11.8 创建test_audio_format.py测试格式转换功能
- [ ] 11.9 测试各种格式的转换（MP3、FLAC、M4A、OGG等）
- [ ] 11.10 测试ffmpeg不可用时的错误处理
- [ ] 11.11 提交音频格式处理代码（commit: `feat: 实现音频格式自动转换功能`）
