## Why

BiliDigest 目前只有处理端点（`/api/v1/process`），处理结果存储在本地 `results/` 目录中，
但无法在线浏览、查看或管理。随着已处理视频数量增长（当前 28 个），需要一个 Web 管理界面。

## What Changes

- 新增 Web 管理界面，合并到现有 FastAPI 服务（端口 8000）
- 视频列表页：展示所有已处理视频，支持按标题/UP主搜索
- 视频详情页：展示文字稿、翻译、整理版、摘要，支持音频播放
- 删除功能：删除单个视频的所有处理结果
- 重处理功能：重新触发已有视频的处理流程

## Capabilities

### New Capabilities

- `admin-ui`: Web 管理界面，提供视频列表浏览、详情查看、搜索、删除和重处理

### Modified Capabilities

- `result-storage`: ResultStorage 新增 list_videos() 方法

## Impact

- 依赖：新增 jinja2
- 代码：新增 src/admin/；修改 main.py, storage.py, pyproject.toml
- 端口：复用 8000，无新增
