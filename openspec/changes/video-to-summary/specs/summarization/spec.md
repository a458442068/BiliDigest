## ADDED Requirements

### Requirement: 生成文字稿摘要
系统SHALL基于文字稿生成内容摘要。

#### Scenario: 生成中文摘要
- **WHEN** 文字稿为中文
- **THEN** 系统生成中文摘要

#### Scenario: 生成英文摘要
- **WHEN** 文字稿为英文且未翻译
- **THEN** 系统生成英文摘要

#### Scenario: 基于翻译生成摘要
- **WHEN** 文字稿为英文且已翻译为中文
- **THEN** 系统基于中文翻译生成摘要

### Requirement: 支持多种LLM后端
系统SHALL支持通过配置选择不同的LLM后端进行摘要生成。

#### Scenario: 使用OpenAI API
- **WHEN** 配置LLM_PROVIDER为openai并提供OPENAI_API_KEY
- **THEN** 系统使用OpenAI API生成摘要

#### Scenario: 使用本地LLM
- **WHEN** 配置LLM_PROVIDER为local
- **THEN** 系统使用本地部署的LLM生成摘要

#### Scenario: LLM后端不可用
- **WHEN** 配置的LLM后端无法访问或返回错误
- **THEN** 系统返回SummarizationError，错误码为LLM_API_ERROR

### Requirement: 摘要可选
系统SHALL将摘要生成作为可选功能。

#### Scenario: 用户请求摘要
- **WHEN** 用户在options中设置summarize为true
- **THEN** 系统生成摘要

#### Scenario: 用户不请求摘要
- **WHEN** 用户在options中设置summarize为false或未设置
- **THEN** 系统跳过摘要生成步骤

### Requirement: 摘要质量
系统SHALL生成简洁且信息丰富的摘要。

#### Scenario: 长文字稿摘要
- **WHEN** 文字稿内容较长
- **THEN** 系统生成涵盖主要观点的简洁摘要

#### Scenario: 短文字稿摘要
- **WHEN** 文字稿内容较短
- **THEN** 系统生成概括主要内容的摘要

#### Scenario: 摘要长度控制
- **WHEN** 生成摘要
- **THEN** 摘要长度适中，不宜过长或过短
