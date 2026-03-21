## ADDED Requirements

### Requirement: 支持BV号输入
系统SHALL支持通过BV号下载B站视频音频。

#### Scenario: BV号格式正确且视频存在
- **WHEN** 用户提供有效的BV号（如BV1xx411c7mD）
- **THEN** 系统下载该视频的音频并返回音频文件路径

#### Scenario: BV号格式错误
- **WHEN** 用户提供格式错误的BV号
- **THEN** 系统返回DownloadError，错误码为INVALID_BV_FORMAT

#### Scenario: 视频不存在
- **WHEN** 用户提供的BV号对应的视频不存在或已被删除
- **THEN** 系统返回DownloadError，错误码为VIDEO_NOT_FOUND

### Requirement: 支持完整URL输入
系统SHALL支持通过完整的B站视频URL下载音频。

#### Scenario: URL格式正确且视频存在
- **WHEN** 用户提供有效的B站视频URL
- **THEN** 系统下载该视频的音频并返回音频文件路径

#### Scenario: URL格式错误
- **WHEN** 用户提供非B站的URL或格式错误的URL
- **THEN** 系统返回DownloadError，错误码为INVALID_URL

### Requirement: 仅下载音频流
系统SHALL仅下载视频的音频流，不下载视频流。

#### Scenario: 下载音频
- **WHEN** 用户请求下载视频
- **THEN** 系统仅下载音频流，输出为wav格式文件

### Requirement: 支持需要登录的视频
系统SHALL支持通过cookie下载需要登录才能访问的视频。

#### Scenario: 视频需要登录但未配置cookie
- **WHEN** 视频需要登录但未配置BILIBILI_COOKIE环境变量
- **THEN** 系统返回DownloadError，错误码为AUTH_REQUIRED

#### Scenario: 视频需要登录且已配置cookie
- **WHEN** 视频需要登录且已配置有效的BILIBILI_COOKIE
- **THEN** 系统使用cookie下载视频音频

### Requirement: 网络错误处理
系统SHALL正确处理网络相关错误。

#### Scenario: 网络超时
- **WHEN** 下载过程中网络超时
- **THEN** 系统返回DownloadError，错误码为NETWORK_TIMEOUT

#### Scenario: 网络连接失败
- **WHEN** 无法连接到B站服务器
- **THEN** 系统返回DownloadError，错误码为NETWORK_ERROR

### Requirement: 音频格式标准化
系统SHALL确保下载的音频格式是STT支持的格式，并进行必要的预处理。

#### Scenario: 下载格式支持且采样率正确
- **WHEN** yt-dlp下载的音频格式为STT支持的格式（WAV、MP3、FLAC、M4A）且采样率为16kHz
- **THEN** 系统直接返回该音频文件

#### Scenario: 下载格式支持但采样率不正确
- **WHEN** yt-dlp下载的音频格式为STT支持的格式但采样率不是16kHz
- **THEN** 系统使用ffmpeg重采样到16kHz单声道并返回转换后的文件

#### Scenario: 下载格式不支持，转换成功
- **WHEN** yt-dlp下载的音频格式不被STT支持
- **THEN** 系统使用ffmpeg转换为WAV格式（16kHz单声道）并返回转换后的文件

#### Scenario: 下载格式不支持，转换失败
- **WHEN** yt-dlp下载的音频格式不被STT支持且ffmpeg转换失败
- **THEN** 系统返回DownloadError，错误码为FORMAT_CONVERSION_ERROR

#### Scenario: ffmpeg不可用
- **WHEN** 系统未安装ffmpeg或ffmpeg命令执行失败
- **THEN** 系统返回DownloadError，错误码为FFMPEG_NOT_AVAILABLE
