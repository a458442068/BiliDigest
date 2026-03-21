## 1. 基础设施

- [x] 1.1 config.py 添加 result_dir 配置项（默认 ./results）
- [x] 1.2 .env.example 添加 RESULT_DIR 示例
- [x] 1.3 .env 添加 RESULT_DIR 配置
- [x] 1.4 提交配置变更（commit: `feat: 添加结果存储目录配置`）

## 2. 工具模块

- [x] 2.1 实现 src/utils/bv.py（BV号提取、分P列表获取）
- [x] 2.2 实现 src/utils/storage.py（ResultStorage类：缓存检查、保存、加载、重命名）
- [x] 2.3 提交工具代码（commit: `feat: 实现BV提取和结果存储工具`）

## 3. 模型层

- [x] 3.1 ProcessOptions 添加 force 字段（默认 false）
- [x] 3.2 ProcessResult 添加 result_dir、cached_steps 字段
- [x] 3.3 提交模型变更（commit: `feat: 扩展API模型支持缓存控制`）

## 4. 流水线改造

- [x] 4.1 downloader.py 移除 --no-playlist，支持分P，返回分P列表
- [x] 4.2 pipeline.py 集成存储（每步落盘、缓存检查）
- [x] 4.3 实现配置变化检测（stt_model, llm_model 对比）
- [x] 4.4 实现旧文件重命名逻辑（用旧模型名）
- [x] 4.5 提交流水线变更（commit: `feat: 流水线集成缓存断点续跑`）

## 5. API层

- [x] 5.1 routes.py 传递 force 参数到 pipeline
- [x] 5.2 routes.py 返回 result_dir 和 cached_steps
- [x] 5.3 提交API变更（commit: `feat: API支持force参数和缓存信息返回`）

## 6. 测试

- [x] 6.1 单P视频全流水线测试（首次处理）
- [x] 6.2 单P视频缓存命中测试（再次请求）
- [x] 6.3 多P视频测试
- [x] 6.4 配置变化重跑测试（换模型后检测重命名）
- [x] 6.6 部分失败后重试测试
- [x] 6.7 提交测试代码（commit: `test: 添加本地存储和缓存测试`）
