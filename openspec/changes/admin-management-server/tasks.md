## 1. 基础设施

- [x] 1.1 在 `pyproject.toml` 添加 `jinja2` 依赖
- [x] 1.2 在 `src/utils/storage.py` 新增 `list_videos()` 方法，扫描 results 目录返回视频元数据列表
- [x] 1.3 创建 `src/admin/__init__.py`

## 2. 路由与业务逻辑

- [x] 2.1 创建 `src/admin/routes.py`，实现 GET `/admin/` 列表路由（含搜索 `?q=` 过滤）
- [x] 2.2 实现 GET `/admin/video/{bv_id}` 详情路由，读取并传递 transcript/translation/summary 内容到模板
- [x] 2.3 实现 POST `/admin/video/{bv_id}/delete` 删除路由，调用 storage 删除目录后重定向列表
- [x] 2.4 实现 POST `/admin/video/{bv_id}/reprocess` 重处理路由，用 BackgroundTasks 异步调用 pipeline.process()

## 3. 模板

- [x] 3.1 创建 `src/admin/templates/base.html` 基础布局（Tailwind CDN + 导航栏 + 页面结构）
- [x] 3.2 创建 `src/admin/templates/list.html` 列表页（搜索框 + 视频表格）
- [x] 3.3 创建 `src/admin/templates/detail.html` 详情页（视频信息 + 标签切换显示文字稿/翻译/摘要 + 音频播放器 + 操作按钮）

## 4. 集成

- [x] 4.1 修改 `main.py`，配置 Jinja2Templates 模板目录，注册 admin 路由，挂载 results 目录的音频文件静态访问
