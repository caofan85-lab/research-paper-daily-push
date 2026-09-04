# research-paper-daily-push：每日科研文献雷达

[![Python unittest](https://github.com/caofan85-lab/research-paper-daily-push/actions/workflows/unittest.yml/badge.svg)](https://github.com/caofan85-lab/research-paper-daily-push/actions/workflows/unittest.yml)

这是一个开源的 Codex Skill。用户可以把3–10篇代表性论文放入本地目录，由 Skill 提取论文内容、生成带证据映射的研究画像草案，并在用户确认后据此检索近期论文。候选论文经过初筛、证据复核、评分、去重和中文总结后，只推荐真正值得阅读的少量论文。项目也支持专业术语双重解释、微信推送、本地推送历史和研究记忆。

公开模板**不包含任何预设研究主题、访问凭据、推送历史或学习记录**。在完成研究配置前，程序会停止检索，避免返回无关论文。

> 第一次接触 Python、Git 或 Codex Skill？请直接阅读[小白安装与使用指南](references/installation_guide.md)。

## 主要功能

- 优先检索近24小时论文；高分候选不足时自动扩展到最近7天。
- 从 PDF、DOCX、TXT 或 Markdown 代表性论文中生成可追溯的研究画像草案。
- 激活画像前必须由用户确认；已有正式画像不会因新增论文而静默改变。
- 使用 Europe PMC、Crossref、Semantic Scholar、OpenAlex 和 bioRxiv 等稳定学术接口。
- 按研究相关性、创新性、论文质量、方法学价值和研究启发进行透明初筛。
- 要求 Codex 阅读可用证据后重新评分，避免仅凭关键词或题名推荐。
- 默认只推荐评分不低于70分的5–10篇论文，允许少于5篇或零推荐。
- 按 DOI 优先、规范化题名兜底的方式去重，已经推送的论文不会作为新论文重复发送。
- 生成中文每日文献雷达、前三名推荐、研究灵感和专业术语双重解释。
- 支持 WxPusher、Server酱和企业微信机器人，并在未配置推送时继续生成本地报告。

## 运行环境

- Python 3.10 或更高版本。
- PDF 文本提取使用 `pypdf`；DOCX、TXT 和 Markdown 提取及其余核心流程使用 Python 标准库。
- 联网检索和消息推送需要运行环境能够访问相应学术接口与通知服务。
- [OpenAlex API](https://help.openalex.org/api/) 支持匿名基础检索；需要更高调用额度时，可申请 API Key 并存入 `OPENALEX_API_KEY` 环境变量，也可用 `OPENALEX_MAILTO` 提供联系邮箱。OpenAlex 检索使用游标翻页，每条查询最多读取600条近期记录。

## 安装

下面是快速安装方式。需要逐步截图式文字说明、安装检查、首次配置和常见问题时，请阅读[小白安装与使用指南](references/installation_guide.md)。

可以克隆仓库：

```powershell
git clone https://github.com/caofan85-lab/research-paper-daily-push.git
cd research-paper-daily-push
python -m pip install -r requirements.txt
```

也可以下载 ZIP，然后把整个 `research-paper-daily-push` 文件夹复制到 Codex 的 Skills 目录。

## 配置研究方向

### 推荐方式：从代表性论文自动建立画像

1. 将3–10篇最能代表本人研究方向的论文放入 `user_papers/`。支持 PDF、DOCX、TXT 和 Markdown，也可以使用子文件夹。
2. 在 Codex 中发送：“使用 `$research-paper-daily-push` 读取 `user_papers` 中的论文，生成研究画像草案。”
3. Skill 会在本地提取论文文字，综合识别研究对象、核心问题、实验方法、组学类型、关键实体和检索词，并为核心判断记录来源文件与原文片段。
4. 检查 Skill 展示的高置信度方向、低置信度判断和待确认问题。明确确认后，Skill 才会把画像写入 `config/research_profile.local.json` 并启用检索。

完整的数据结构、校验和确认流程见 [`references/profile_from_papers.md`](references/profile_from_papers.md)。扫描版 PDF 如果无法提取文字，需要先进行 OCR 或换用可检索版本。

### 备用方式：手动描述研究方向

没有代表性论文时，可以直接向 Codex 说明研究对象、核心科学问题、优先方法和排除规则。Codex 按照 [`references/profile_schema.md`](references/profile_schema.md) 生成 `config/research_profile.local.json` 和 `config/research_topics.local.md`，展示给用户确认后再将 `configured` 改为 `true`。

公开模板默认留空。`user_papers/` 中的论文、提取文本、草案和 `.local` 配置默认被 Git 忽略。请勿强制提交版权论文、个人研究主题、未公开研究计划或真实推送凭据。

## 配置 WxPusher 微信推送

完整的应用创建、微信 ClawBot 绑定与激活、UID获取、环境变量设置、双端测试和故障排查步骤见 [`references/wxpusher_setup.md`](references/wxpusher_setup.md)。Windows 新手推荐使用其中的“从剪贴板自动读取”方法，避免手动粘贴时漏字符或复制进多余网页内容；检查过程不会回显真实 Token 和 UID。

ClawBot 是 WxPusher 的额外接收渠道：绑定后项目仍使用原来的 `appToken + UID`，不需要配置新的 ClawBot Token。按照 WxPusher 当前规则，ClawBot 每次激活可在 24 小时内接收最多 10 次推送，过期或用完后需在微信会话中回复任意内容重新激活；详细限制请以 [WxPusher 官方文档](https://wxpusher.zjiecode.com/docs/)为准。

配置后先进行本地检查：

```powershell
python scripts/push_wechat.py --provider wxpusher --check-config
```

确认无误后发送真实测试消息：

```powershell
python scripts/push_wechat.py --provider wxpusher --test-message
```

第一条命令不会联网发送，也不会显示 Token 或 UID；第二条命令会产生真实外部推送。

## 运行文献雷达

### 第一步：检索并生成复核队列

```powershell
python scripts/run_daily.py collect --mode all
```

结果默认写入 `data/runs/YYYY-MM-DD/review_queue.json`。该文件只包含元数据初筛候选，不能直接当作最终推荐。Codex 需要阅读摘要，并在必要时核对 DOI、出版商页面或全文，然后生成符合 `SKILL.md` 约定的 `reviewed_articles.json`。

### 第二步：生成报告并推送

```powershell
python scripts/run_daily.py deliver --reviewed reviewed_articles.json --report daily-report.md --provider auto
```

当 `WXPUSHER_APP_TOKEN` 和 `WXPUSHER_UID` 均已配置时，`--provider auto` 会优先使用 WxPusher。如需明确限定 WxPusher，请改用 `--provider wxpusher`。

只有报告已经在当前对话中真实展示时，才可以使用：

```powershell
python scripts/run_daily.py deliver --reviewed reviewed_articles.json --report daily-report.md --skip-push --record-local-report
```

该参数会把本地展示视为一次已确认交付，并写入去重历史和研究记忆。

## 定时运行

仓库不预设固定定时任务，因为执行时间、时区、运行设备和外部推送授权因用户而异。创建定时任务时，应明确指定：

- 执行时间和时区；
- 使用的研究配置与检索模式；
- 是否授权自动推送；
- 凭据如何安全注入；
- 电脑关机或休眠时由哪台长期在线设备接替运行。

## 数据与隐私

- `data/pushed_articles.json` 和 `data/research_memory.json` 在公开模板中为空。
- `user_papers/` 中的论文、`data/profile_build/` 中的提取文本和 `config/*.local.*` 不会被提交。
- 论文画像解析默认在本地完成；论文内容不得未经授权上传到外部服务。
- Token、UID、SendKey 和 Webhook 只从环境变量读取。
- 推送状态 JSON 不保存真实凭据。
- `.env`、运行中间文件和交付状态文件不会被提交。
- 发布自己的分支或压缩包前，应再次检查报告、历史记录、本地路径、研究主题、Token 和 UID。

## 开源许可

本项目采用 MIT License。为保持许可证法律文本的准确性，根目录中的 [`LICENSE`](LICENSE) 保留标准英文原文；中文用户可阅读 [`LICENSE.zh-CN.md`](LICENSE.zh-CN.md) 参考译文，解释不一致时以英文原文为准。
