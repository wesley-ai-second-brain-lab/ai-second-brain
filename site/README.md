# 网站模板（可选）

`index.html` 是一个 Claude Artifact 页面，需要 `db`、`user`、`assets` 三个能力。
让 Claude 发布它（例如：「用 site/index.html 发布一个 artifact，开启 db、user、assets 能力」），然后把得到的地址填进 `brain.config.json` 的 `website_url`。

数据集合：
- `library`：学习笔记（视频 `yt-<ID>`、文章 `art-<slug>`、PDF `pdf-<slug>`），字段 `{id,type,title,url,channel,desc,tags,createdAt,notes,mindmap,frames}`
- `days`：每日精选（可选，配合每日早报 skill）
- `marks`：浏览者自己的稍后读 / 收藏 / 点赞 / 笔记
