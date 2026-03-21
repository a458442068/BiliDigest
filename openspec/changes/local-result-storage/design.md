## Context

用户需要在处理视频后保留结果，并支持缓存断点续跑。当前处理结果在请求完成后被删除，无法复用。需要设计一个本地存储系统，支持每步落盘、缓存检查、配置变化检测。

## Goals / Non-Goals

**Goals:**
- 每步处理完成后立即保存结果到本地目录
- 优先使用已有结果，避免重复计算
- 检测配置变化（模型变更），自动重跑受影响步骤
- 支持B站多分P视频
- 保留部分结果（失败时已保存步骤不丢失）

**Non-Goals:**
- 不支持分布式存储（仅本地文件系统）
- 不支持结果版本管理（仅保留当前版本 + 旧模型版本）
- 不自动清理旧结果（用户自行管理磁盘空间）

## Decisions

### 1. 存储目录结构
**选择**: `{RESULT_DIR}/{BV号}/` 下扁平结构

**单P视频**:
```
{RESULT_DIR}/BV1GJ411x7h7/
├── audio.wav
├── transcript.txt
├── translation.txt
├── summary.txt
└── metadata.json
```

**多P视频**:
```
{RESULT_DIR}/BV1GJ411x7h7/
├── P1_audio.wav
├── P1_transcript.txt
├── P2_audio.wav
├── P2_transcript.txt
└── metadata.json
```

**理由**: 扁平结构简单直观，文件名自带分P标识，无需多层目录

### 2. 缓存检查策略
**选择**: 每步执行前检查文件是否存在 + 配置是否一致

**检查逻辑**:
```
has_file = 文件存在
config_match = metadata中记录的模型与当前一致
use_cache = has_file and config_match and not force
```

**理由**: 文件存在是最直接的缓存判断，配置一致确保结果有效性

### 3. 配置变化处理
**选择**: 重命名旧文件，用新配置重跑

**metadata.json 记录**:
- `stt_model`: STT 模型路径
- `llm_model`: LLM 模型名（从 API 响应获取）

**重命名规则**:
- STT 变了 → `transcript.txt` → `transcript_{旧模型名}.txt`
- LLM 变了 → `translation.txt` → `translation_{旧模型名}.txt`, `summary.txt` → `summary_{旧模型名}.txt`

**理由**: 保留旧结果供参考，新结果覆盖主文件

### 4. 分P处理
**选择**: 移除 `--no-playlist`，获取所有分P，逐个处理

**BV号提取**: 从 URL 或直接输入中提取 `BV[1-9A-HJ-NP-Za-km-z]{10}`
**分P列表**: yt-dlp `--flat-playlist` 获取分P信息

**理由**: 用户需要处理全部分P内容

### 5. 落盘时机
**选择**: 每步完成后立即保存，不等全部完成

**流程**:
1. 下载 → 保存 audio.wav → 继续
2. STT → 保存 transcript.txt → 继续
3. 翻译 → 保存 translation.txt → 继续
4. 摘要 → 保存 summary.txt → 完成

**理由**: 避免中间失败导致所有结果丢失

## Risks / Trade-offs

### 风险1: 磁盘空间耗尽
**影响**: 无法保存新结果
**缓解措施**: 在文档中说明磁盘需求，建议定期清理旧结果

### 风险2: 并发写入冲突
**影响**: 多个请求同时处理同一BV可能导致文件冲突
**缓解措施**: 当前为单用户场景，暂不处理；后续可添加文件锁

### 风险3: metadata.json 不一致
**影响**: 进程崩溃时metadata可能未更新
**缓解措施**: 每步落盘时更新metadata，允许部分更新
