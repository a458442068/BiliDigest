## ADDED Requirements

### Requirement: 英文翻译为中文
系统SHALL支持将英文文字稿翻译为中文。

#### Scenario: 翻译英文内容
- **WHEN** 文字稿语言为英文且用户请求翻译
- **THEN** 系统返回中文翻译结果

#### Scenario: 非英文内容不翻译
- **WHEN** 文字稿语言不是英文
- **THEN** 系统返回原始文字稿，translation字段为空

### Requirement: 支持多种LLM后端
系统SHALL支持通过配置选择不同的LLM后端进行翻译。

#### Scenario: 使用OpenAI API
- **WHEN** 配置LLM_PROVIDER为openai并提供OPENAI_API_KEY
- **THEN** 系统使用OpenAI API进行翻译

#### Scenario: 使用本地LLM
- **WHEN** 配置LLM_PROVIDER为local
- **THEN** 系统使用本地部署的LLM进行翻译

#### Scenario: LLM后端不可用
- **WHEN** 配置的LLM后端无法访问或返回错误
- **THEN** 系统返回TranslationError，错误码为LLM_API_ERROR

### Requirement: 翻译可选
系统SHALL将翻译作为可选功能。

#### Scenario: 用户请求翻译
- **WHEN** 用户在options中设置translate为true
- **THEN** 系统对英文内容进行翻译

#### Scenario: 用户不请求翻译
- **WHEN** 用户在options中设置translate为false或未设置
- **THEN** 系统跳过翻译步骤

### Requirement: 保持原文含义
系统SHALL尽量保持翻译的准确性。

#### Scenario: 专业术语翻译
- **WHEN** 文字稿包含专业术语
- **THEN** 系统尽量使用准确的专业术语翻译

#### Scenario: 口语化表达翻译
- **WHEN** 文字稿包含口语化表达
- **THEN** 系统尽量保持口语化风格进行翻译
