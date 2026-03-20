# STT Server - B站视频转文字摘要服务

## 简介

一个自动化工具，从B站视频链接提取音频，通过Qwen3-ASR模型转换为文字，支持英文翻译和摘要生成。

## 功能

- B站视频音频下载（支持BV号和URL）
- 语音识别（Qwen3-ASR-1.7B）
- 英文翻译为中文（占位）
- 内容摘要生成（占位）
- RESTful API服务

## 安装

```bash
# 克隆项目
git clone <repo-url>
cd STT-server

# 安装依赖
uv sync

# 复制环境配置
cp .env.example .env
```

## 配置

编辑 `.env` 文件：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `BILIBILI_COOKIE` | B站Cookie（可选） | 空 |
| `QWEN_ASR_MODEL_PATH` | 模型路径 | `Qwen/Qwen3-ASR-1.7B` |
| `LLM_PROVIDER` | LLM后端 | `openai` |
| `OPENAI_API_KEY` | OpenAI API Key | 空 |
| `PORT` | 服务端口 | `8000` |

## 运行

```bash
uv run python main.py
```

## API

### POST /api/v1/process

处理B站视频，返回文字稿。

```bash
curl -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{"url": "BV1xx411c7mD", "options": {"translate": false, "summarize": false}}'
```

### GET /api/v1/health

健康检查接口。

```bash
curl http://localhost:8000/api/v1/health
```

## 测试

```bash
uv run pytest tests/
```
