## 1. 配置

- [x] 1.1 config.py 添加 stt_backend、stt_api_url、stt_api_key
- [x] 1.2 .env.example 添加 STT 环境变量示例
- [x] 1.3 .env 添加 STT 环境变量
- [x] 1.4 提交配置变更

## 2. STT 服务改造

- [x] 2.1 实现 _transcribe_remote() 方法（调用 OpenAI-compatible API）
- [x] 2.2 改造 transcribe() 支持 default/local/remote 模式
- [x] 2.3 实现双端失败错误处理（不重试，记录关键信息）
- [x] 2.4 提交 STT 服务变更

## 3. 测试

- [x] 3.1 default 模式：本地成功测试
- [x] 3.2 remote 模式测试
- [x] 3.3 双端失败错误信息测试
- [x] 3.4 提交测试代码
