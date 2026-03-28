## Context

BiliDigest 是一个视频理解服务，当前通过 `/api/v1/process` 接口处理 B站视频，结果存储在 `results/{BV_ID}/` 目录。
已处理 28 个视频，每个视频包含 audio.wav、transcript.txt、translation.txt、transcript_clean.txt、summary.txt、metadata.json。

当前缺少在线浏览和管理能力，用户需要手动操作文件系统来查看结果。

## Goals / Non-Goals

**Goals:**
- 提供 Web 界面浏览所有已处理视频
- 支持按标题/UP主搜索
- 查看每个视频的完整处理结果（文字稿、翻译、摘要）
- 支持音频在线播放
- 支持删除和重处理操作

**Non-Goals:**
- 不提供用户认证/权限管理（单用户场景）
- 不新增独立端口，合并到现有 8000 端口
- 不处理批量操作（批量删除、批量重处理）
- 不提供文件下载功能

## Decisions

### 1. 技术方案：FastAPI + Jinja2 模板

**选择**: 在现有 FastAPI 服务中添加 `/admin` 路由，使用 Jinja2 模板渲染页面。

**理由**:
- 同一语言（Python），复用现有 ResultStorage 和 ProcessingPipeline
- 零新增端口，部署简单
- Jinja2 轻量，不需要前端构建工具

**备选方案**:
- 独立前端 + API：开发复杂度高，对当前需求过度设计
- 纯静态 HTML：不适合动态内容渲染

### 2. 前端样式：Tailwind CSS CDN

**选择**: 使用 Tailwind CSS CDN，不引入 npm 构建。

**理由**:
- 零构建依赖，HTML 内联即用
- 快速实现美观的响应式布局
- 不需要额外的前端工程化

### 3. 数据获取：遍历 results 目录

**选择**: `list_videos()` 方法遍历 `results/` 目录，读取每个 metadata.json。

**理由**:
- 无需维护索引/数据库
- 28 个视频，O(n) 扫描性能可接受
- 数据源与现有存储完全一致

### 4. 重处理实现：异步后台任务

**选择**: 使用 `BackgroundTasks` 异步调用 `pipeline.process()`。

**理由**:
- 处理可能耗时数分钟，不能阻塞 HTTP 请求
- FastAPI 原生支持 BackgroundTasks
- 处理结果通过文件系统持久化，无需 WebSocket 推送

## Risks / Trade-offs

- [大量视频时列表加载慢] → 可加分页，当前 28 个无需考虑
- [重处理期间无实时进度反馈] → 后续可通过 WebSocket 增强，当前用页面刷新
- [并发删除/重处理冲突] → 单用户场景下概率极低
- [模板内联 CSS 导致文件较大] → Tailwind CDN 可接受，后续可提取 static CSS
