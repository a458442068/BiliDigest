# BiliDigest - 视频转文字摘要服务

## 简介

自动化工具，从视频链接提取音频，通过 Qwen3-ASR 模型转换为文字，支持翻译、摘要生成和字幕导出。

## 功能

- 多平台视频下载（B站、YouTube、Twitter、TikTok、SoundCloud 等）
- 语音识别（Qwen3-ASR-1.7B，支持可选词级时间戳）
- 翻译为中文（OpenAI-compatible LLM）
- 内容摘要生成
- SRT / VTT 字幕导出
- 处理进度实时查询
- Web 管理界面（支持暗色主题）

## 安装

```bash
git clone <repo-url>
cd STT-server
uv sync
cp .env.example .env
```

## 配置

编辑 `.env` 文件：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `BILIBILI_COOKIE` | B站Cookie（可选） | 空 |
| `QWEN_ASR_MODEL_PATH` | STT 模型路径 | `Qwen/Qwen3-ASR-1.7B` |
| `STT_TIMESTAMPS` | 启用时间戳（需加载对齐模型） | `false` |
| `FORCED_ALIGNER_PATH` | 对齐模型路径 | `Qwen/Qwen3-ForcedAligner-0.6B` |
| `LLM_PROVIDER` | LLM后端 | `openai` |
| `OPENAI_API_KEY` | OpenAI API Key | 空 |
| `OPENAI_BASE_URL` | OpenAI Base URL | `https://api.openai.com/v1` |
| `LLM_MODEL` | LLM 模型名称 | `gpt-4o-mini` |
| `STT_BACKEND` | STT后端 (default/local/remote) | `default` |
| `PORT` | 服务端口 | `8000` |
| `CORS_ORIGINS` | 允许跨域来源（逗号分隔） | `http://localhost:8000,http://127.0.0.1:8000` |

## 运行

```bash
uv run python main.py
```

## API

### POST /api/v1/process

处理视频，返回文字稿。

```bash
curl -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=xxx", "options": {"translate": true, "summarize": true}}'
```

### GET /api/v1/status/{bv_id}

查询处理进度。

```bash
curl http://localhost:8000/api/v1/status/BV1xx411c7mD
```

### GET /api/v1/export/{bv_id}/srt

导出 SRT 字幕（可选 `?part=N`）。

```bash
curl http://localhost:8000/api/v1/export/BV1xx411c7mD/srt -o subtitle.srt
```

### GET /api/v1/export/{bv_id}/vtt

导出 VTT 字幕。

### GET /api/v1/health

健康检查。

### 异步任务接口

浏览器脚本和长视频建议使用异步任务接口，避免长时间占用浏览器请求：

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"url":"BV1xx411c7mD","options":{"translate":true,"summarize":true,"target_parts":[1]}}'

curl http://localhost:8000/api/v1/jobs/{job_id}
curl http://localhost:8000/api/v1/jobs/{job_id}/result
```

`options.summary_template` 支持 `general`、`notes`、`meeting` 和 `study`。结构化摘要会额外保存关键观点、章节、行动项和实体，并在 JSON/Markdown 导出中提供。

摘要模型不要求必须返回 JSON。服务支持标准 JSON，以及小模型更容易遵守的 `摘要：`、`关键观点：`、`行动项：` 三段格式；模型输出普通文本时也会降级保存为摘要，原始文字稿会直接保留。

### 浏览器脚本

`userscript/bilibili-ai-processor.user.js` 可安装到 Tampermonkey。脚本支持当前页面 BV 号、当前 P/全部 P、异步进度查询和结果展示。首次使用时在面板中设置本地服务地址，默认是 `http://localhost:8000`。

## Web 管理界面

访问 `http://localhost:8000/admin/` 查看已处理视频列表、详情、搜索、删除和重新处理。

> 本项目按本机/可信内网工具设计，默认不提供 admin 鉴权。请不要在公网裸露 `/admin/` 或 `/results/`。

## 支持的站点

B站、YouTube、Twitter/X、TikTok、Reddit、SoundCloud、Vimeo、Twitch、Instagram、网易云音乐、喜马拉雅、小宇宙等。详见 `src/utils/bv.py` 中的 `SUPPORTED_DOMAINS`。

## 测试

```bash
uv run --with pytest pytest tests/
```

默认测试使用 mock/fake 服务，不会访问真实下载、STT 模型或 LLM API。需要验证真实外部链路时，使用 `integration` 标记单独运行：

```bash
uv run --with pytest pytest -m integration
```
