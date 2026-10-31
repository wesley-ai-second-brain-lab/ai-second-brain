# AI 第二大脑 · 使用说明

这是按 Karpathy「LLM 知识库」方式搭的个人学习库，由 Claude 维护。

## 结构
- `raw/`：原始资料存档（文章全文、视频字幕、PDF 文字），原样保留、不改动。
- `sources/`：每份资料一页：一句话、Highlights / 要点（视频带时间戳和截图）、关键概念、对我的启发、相关概念、原文出处。文件名 `YYYY-MM-DD-slug.md`。
- `wiki/`：按概念整理的页面。每收录一份新资料，就更新相关概念页（新增要点并链接回来源），必要时新建概念页。
- `assets/<slug>/`：视频关键截图，嵌在 sources 页里。
- `inbox/`：视频处理结果；`inbox/queue/` 是待处理队列，`inbox/logs/` 是日志。
- `tools/`：视频工具（claude-watch、runner.py）。
- `index.md`：总目录，所有概念和资料各一行。
- `brain.config.json`：Google Drive 文件夹、网站地址等配置。

## 规则
- 链接用 Obsidian 的 `[[页面名]]` 写法，在 Obsidian 里可以看关系图谱。
- 每个结论都要能追溯到 sources 里的某一页；sources 能追溯到原文链接或 raw。
- 中文写作，用自己的话概括，不大段复制原文。

## 怎么用
- 收录：把 YouTube 链接、文章链接、PDF 或粘贴的全文发给 Claude，说「存进第二大脑」。
- 提问：直接问，比如「我存过的资料里，Agent 记忆怎么设计？」Claude 会先读 index，再读相关页面回答，并注明出处。
- 在 Obsidian 里看：从 `index.md` 开始；或 ⌘+Shift+F 搜视频 ID / 标题关键词。
