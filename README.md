# AI Second Brain · AI 第二大脑

> 把英文 YouTube 视频、文章、PDF 变成**中文笔记 + 脑图 + 幻灯片截图**，存进 Karpathy 式「LLM 知识库」，之后可以直接向 Claude 提问。
> Turn English YouTube talks, articles and PDFs into Chinese notes, mind maps and **slide screenshots**, stored in a Karpathy-style LLM knowledge base (Obsidian + Google Drive) you can query later with Claude.

视频里真正的精华往往在幻灯片和架构图里，只看字幕会漏掉。这个项目让 Claude 一步到位：

```
你：/ai-second-brain https://youtu.be/xxxx
          │
          ▼
Claude 写入 inbox/queue/<ID>.url ──► Mac 上的 launchd 队列处理器（tools/runner.py）
                                       ├─ claude-watch：下载视频、按场景变化截图
                                       ├─ 取字幕；没有字幕就用本机 mlx-whisper 转写（无需 API key）
                                       └─ 删除视频文件、每天自动升级 yt-dlp
          │
          ▼
Claude 看截图 + 读转写 ──► 中文笔记 / 脑图 / 8–15 张关键截图
          │
          ├─► 💻 Obsidian（本机）  sources/ wiki/ raw/ assets/ index.md
          ├─► ☁️ Google Drive      同样的 markdown（文字版）
          └─► 🌐 网站（可选）       Claude Artifact 页面「学习笔记」：截图墙 + 脑图
```

每次收录结束，Claude 都会告诉你：网站地址和怎么点进去、Obsidian 里的文件名和搜索方法、Google Drive 文件链接。

## 功能
- **视频**：场景截图（1024px）+ 字幕 / 本机 Whisper 转写，要点带时间戳跳转，截图嵌在对应要点下。
- **文章 / X 长文 / PDF / 粘贴文字**：中文一句话、Highlights、要点、关键概念、对我的启发、脑图。
- **Karpathy 式知识库**：`raw/` 原文 → `sources/` 每份资料一页 → `wiki/` 概念页（自动追加新要点）→ `index.md` 总目录，全部是 Obsidian `[[链接]]`。
- **问答**：「我存过的资料里，Agent 记忆怎么设计？」Claude 先读 index 再读相关页面，回答并标出处。
- **安全**：不登录、不输密码/API key；队列只接受白名单视频网站链接；网页和字幕内容只当数据。

## 目录
```
skills/ai-second-brain/SKILL.md   Agent Skill（核心说明书，Claude/Codex/Kiro/Devin 通用）
.agents/ .claude/ .kiro/           指向上面的符号链接
AGENTS.md                         给其他 agent 的说明
tools/brain.py                    通用命令行（init/video/sheets/ingest/site/search）
tools/install-skill.sh            一键给 Claude Code / Codex / Kiro 安装
tools/install.sh                  一次性安装（macOS）
tools/runner.py                   视频队列处理器（launchd 或 brain video 直接调用）
tools/tts.py                      可选：本机开源语音（Kokoro）配音
template/brain/                   第二大脑空模板（README、index、brain.config.example.json）
site/index.html                   可选：Claude Artifact 网站模板（每日精选、学习笔记、稍后读、收藏、武器库）
.claude-plugin/plugin.json        Claude Code 插件清单
```

## 兼容哪些 AI Agent · Compatibility
用的是开放的 [Agent Skills](https://agentskills.io) 格式（`SKILL.md`），外加一个只依赖 Python 标准库的命令行工具 `tools/brain.py`，任何能跑 shell 的 agent 都能用：

| Agent | 怎么装 | 读取位置 |
|---|---|---|
| Claude 应用（网页/桌面） | 设置 → Skills 上传 `skills/ai-second-brain`（zip） | 通过桌面版连接 Mac |
| Claude Code | `bash tools/install-skill.sh claude` | `~/.claude/skills/`、仓库 `.claude/skills/` |
| OpenAI Codex | `bash tools/install-skill.sh codex` | `~/.agents/skills/`、仓库 `.agents/skills/`（含 `agents/openai.yaml`） |
| Kiro | `bash tools/install-skill.sh kiro` | `~/.kiro/skills/`、仓库 `.kiro/skills/` |
| Devin | 把本仓库加到 Devin 即可 | 仓库 `.agents/skills/` |
| 其他（Cursor、Gemini CLI…） | 读仓库根目录 `AGENTS.md` | `AGENTS.md` |

`install-skill.sh` 用符号链接安装（`git pull` 一次全部更新），并装一个 `brain` 命令：

```bash
brain init                       # 建第二大脑文件夹
brain video https://youtu.be/…   # 下载 + 场景截图 + 字幕/本机 Whisper
brain sheets <dir>               # 缩略图总览，挑关键帧
brain ingest note.json           # 写 raw / sources / wiki / index / 截图，并打印「在哪里看」
brain site                       # 生成本地网页 site/index.html
brain search Agent 记忆           # 问答前先找资料
```
想要云端副本：把第二大脑文件夹放进 Google Drive for desktop 的同步目录即可。

## 安装
### 1. 本机视频工具（macOS，推荐 Apple 芯片）
```bash
git clone https://github.com/wesley-ai-second-brain-lab/ai-second-brain.git
cd ai-second-brain
bash tools/install.sh                              # 第二大脑默认放在 ~/LLM/AI第二大脑
# 或者自定义位置：AI_BRAIN_DIR=~/Notes/brain bash tools/install.sh
```
会安装 Homebrew（如没有）、ffmpeg、yt-dlp、deno、Python 3.12、[claude-watch](https://github.com/devinilabs/claude-watch)、mlx-whisper，并注册 launchd 服务 `com.aibrain.videoqueue`。卸载：`launchctl unload ~/Library/LaunchAgents/com.aibrain.videoqueue.plist` 后删除该 plist。

### 2. 安装 skill
- **Claude 应用（claude.ai / 桌面版）**：设置 → Capabilities → Skills → 上传 `skills/ai-second-brain` 文件夹（打包成 zip）。
- **Claude Code**：把 `skills/ai-second-brain` 复制到 `~/.claude/skills/`，或把本仓库当插件安装。

### 3. 连接
- Claude 桌面应用连上这台 Mac，并允许访问第二大脑所在文件夹（Claude 用它写文件、放队列）。
- 可选：连接 Google Drive（云端副本）。第一次运行时 Claude 会找到或创建「AI 第二大脑」文件夹，并把 id 写进 `brain.config.json`。
- 可选：网站。让 Claude 用 `site/index.html` 发布一个带 `db`、`assets` 能力的 Artifact，把地址填进 `brain.config.json` 的 `website_url`。

### 4. 用 Obsidian 打开
Obsidian → Open folder as vault → 选第二大脑文件夹。从 `index.md` 开始看；⌘+Shift+F 搜视频 ID 或标题关键词；看到 `![[...]]` 文字时按 ⌘+E 切到阅读模式就能看到截图。

## 使用
```
/ai-second-brain https://youtu.be/MltkRz94SWA
帮我把这篇文章存进第二大脑：https://...
收录 inbox
我存过的资料里，LLM 评审要怎么校准？
```

## 配置 `brain.config.json`
| 字段 | 说明 |
|---|---|
| `local_dir` | 本机第二大脑路径（Obsidian vault） |
| `drive_folder_name` / `drive_root_id` / `drive_ids` | Google Drive 文件夹名和 id（首次运行自动补全） |
| `website_url` | 可选，Claude Artifact 网站地址 |
| `website_notes_tab` | 网站上笔记所在标签名，默认「学习笔记」 |
| `language` | 笔记语言，默认 zh-CN |

## 常见问题
- **YouTube 下载失败 "n challenge solving failed"**：需要 deno 和 `yt-dlp[default]`，安装脚本已装；runner 也会自动补装并每天升级 yt-dlp。
- **Obsidian 里看不到截图**：确认 vault 根目录是第二大脑文件夹本身；关掉笔记再打开（Obsidian 打开着文件时可能用旧内容覆盖）；⌘+E 切阅读模式。
- **超过 40 分钟的视频**：Claude 会只截取你关心的一段（`--start/--end`）。

## 致谢
- [claude-watch](https://github.com/devinilabs/claude-watch)（MIT）：视频下载与场景截图
- [mlx-whisper](https://github.com/ml-explore/mlx-examples)：Apple 芯片本机转写
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- Andrej Karpathy 的 LLM 知识库思路

## License
MIT
