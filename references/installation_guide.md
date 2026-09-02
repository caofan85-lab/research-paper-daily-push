# 小白安装与使用指南

这份教程面向没有使用过 Git、Python 或 Codex Skill 的用户。按照顺序完成即可，不需要先理解代码。

## 先理解这个项目是什么

这个项目不是双击就能运行的普通软件，而是给 Codex 安装的一套“科研助手说明书＋自动化工具”。

- `SKILL.md` 告诉 Codex 如何检索、复核、评分和总结论文。
- `scripts/` 存放检索、评分、去重、生成报告和微信推送工具。
- `references/` 存放研究配置说明和操作教程。
- `data/` 保存本地推送历史和研究记忆。

正常使用时，用户主要负责告诉 Codex“我要找什么”；Codex 负责调用工具并完成证据复核。单独运行检索脚本只能生成候选队列，不能替代 Codex 对论文证据的判断。

## 一、安装前准备

需要准备：

- Codex Desktop；
- Python 3.10 或更高版本；
- 可以访问学术接口的网络；
- Git，可选。不想安装 Git 时可以直接下载 ZIP。

打开 PowerShell，检查 Python：

```powershell
python --version
```

出现类似下面的结果即可：

```text
Python 3.13.13
```

如果提示找不到 `python`，请先安装 Python 3.10 或更高版本。Windows 安装程序中应勾选“Add Python to PATH”，然后重新打开 PowerShell。

如果准备使用 Git，再检查：

```powershell
git --version
```

### 建议申请 Semantic Scholar API Key

Semantic Scholar 允许不带 Key 检索，但匿名请求会与其他用户共享公共调用额度；访问繁忙时可能收到 `429` 限速响应。项目会继续使用其他数据源，不会因此让整次运行失败，但当天候选论文可能减少。

计划每天定时运行时，建议在 [Semantic Scholar Academic Graph API](https://www.semanticscholar.org/product/api) 申请免费的 API Key，并把它保存为当前 Windows 用户的环境变量：

```powershell
[Environment]::SetEnvironmentVariable(
  "SEMANTIC_SCHOLAR_API_KEY",
  "替换为你的API Key",
  "User"
)
```

设置完成后，应完全关闭并重新打开 PowerShell 和 Codex。真实 API Key 不得写入 `.env.example`、脚本、截图或 Git 提交；`.env.example` 中的空变量仅用于说明项目支持哪些配置。

## 二、方法 A：下载 ZIP 安装，最适合新手

1. 打开项目主页：<https://github.com/caofan85-lab/research-paper-daily-push>。
2. 点击绿色的 `Code` 按钮。
3. 点击 `Download ZIP`。
4. 解压下载的压缩包。
5. 将解压后的文件夹改名为 `research-paper-daily-push`。
6. 打开 Windows 文件资源管理器，在地址栏输入 `%USERPROFILE%\.codex\skills` 并按回车。
7. 如果 `skills` 文件夹不存在，可以在 PowerShell 中运行：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills" | Out-Null
```

8. 把整个 `research-paper-daily-push` 文件夹复制到这个 `skills` 文件夹中。

正确结构应该是：

```text
C:\Users\你的用户名\.codex\skills\research-paper-daily-push\SKILL.md
```

不要多套一层文件夹。下面这种结构是错误的：

```text
...\research-paper-daily-push\research-paper-daily-push-main\SKILL.md
```

安装完成后，完全关闭并重新打开 Codex。

## 三、方法 B：使用 Git 安装，方便以后更新

打开 PowerShell，依次运行：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.codex\skills" | Out-Null
Set-Location "$env:USERPROFILE\.codex\skills"
git clone https://github.com/caofan85-lab/research-paper-daily-push.git
```

完成后重新启动 Codex。

如果出现“目标文件夹已经存在”，说明电脑中可能已经安装过该 Skill。不要直接覆盖，先阅读下方“更新与备份”。

## 四、检查是否安装成功

在 PowerShell 中运行：

```powershell
Test-Path "$env:USERPROFILE\.codex\skills\research-paper-daily-push\SKILL.md"
```

返回下面的结果，说明文件位置正确：

```text
True
```

再进入项目目录：

```powershell
Set-Location "$env:USERPROFILE\.codex\skills\research-paper-daily-push"
```

检查命令行工具：

```powershell
python scripts\run_daily.py --help
```

如果能看到中文帮助信息，说明 Python 和项目脚本能够正常启动。

## 五、配置自己的研究方向

公开版本没有预设研究主题。这样可以保护开发者隐私，也能避免其他用户收到不相关论文。

最简单的方法是在 Codex 中发送：

```text
请使用 $research-paper-daily-push 帮我配置研究方向。

我的研究对象是：
我的核心科学问题是：
我优先关注的技术是：
我希望排除的研究是：
```

例如：

```text
请使用 $research-paper-daily-push 帮我配置研究方向。

我的研究对象是某类作物的干旱适应。
重点关注根系性状、转录调控和代谢组学。
排除只有产量比较、缺少机制分析的研究。
```

Codex 会帮助填写：

```text
references/research_topics.md
config/research_profile.json
```

配置完成后，`config/research_profile.json` 中应包含：

```json
"configured": true
```

研究配置、未公开研究计划和推送凭据可能涉及隐私。不要把个人版本直接提交到公开 GitHub 仓库。

## 六、第一次运行

配置完成后，在 Codex 中直接发送：

```text
运行我的每日科研文献雷达
```

还可以使用：

```text
搜索今天值得我阅读的论文
```

```text
搜索最近一周与我的研究方向相关的论文
```

```text
把今天最值得看的论文推送到微信
```

Skill 会依次完成：

1. 检索近期论文；
2. 合并不同来源的重复记录；
3. 排除已经推送的论文；
4. 进行初步评分；
5. 阅读摘要并核实可用证据；
6. 重新评分并筛选最终论文；
7. 生成中文总结、专业解释和大白话解释；
8. 在已经配置通知渠道时推送报告。

如果当天没有论文达到 70 分，最终结果可能少于 5 篇，甚至零推荐。这是“宁缺毋滥”的正常表现，不代表程序失败。

## 七、配置 WxPusher 微信推送

微信推送是可选功能。没有配置时，项目仍会正常生成本地报告，并提示“微信推送尚未配置。”

完整操作见 [WxPusher 微信推送配置](wxpusher_setup.md)。其中单独说明了如何在 WxPusher 客户端通过“我的 → 推送渠道 → 绑定微信 ClawBot”完成微信渠道绑定、如何在微信会话中激活，以及如何分别检查 WxPusher 客户端和 ClawBot 是否都收到消息。

ClawBot 绑定后不需要增加新的项目变量，项目仍然只使用 `appToken + UID`。根据 WxPusher 当前官方规则，每次激活后最多可在 24 小时内接收 10 次 ClawBot 推送，过期或用完后需要在 ClawBot 会话中回复任意内容重新激活。ClawBot 是额外渠道，建议保留 WxPusher 客户端作为接收兜底。

指南还为 Windows 新手提供了“从剪贴板自动读取”方法：先运行配置代码，等程序提示后再分别复制 appToken 和 UID，回到 PowerShell 直接按 Enter，不需要手动粘贴。程序会检查前缀、格式和长度，只在两项都正确时保存，而且不会回显真实凭据。

取得 `AT_` 开头的 appToken 和 `UID_` 开头的 UID 后，应把它们存入当前用户的环境变量，不能写进脚本或提交到 GitHub。

配置后进入项目目录：

```powershell
Set-Location "$env:USERPROFILE\.codex\skills\research-paper-daily-push"
```

先进行本地检查，不发送消息：

```powershell
python scripts\push_wechat.py --provider wxpusher --check-config
```

配置正确时会显示：

```text
配置有效：通知渠道=wxpusher；接收者数量=1。未输出任何凭据。
```

然后发送真实测试消息：

```powershell
python scripts\push_wechat.py --provider wxpusher --test-message
```

## 八、设置每天自动运行

可以在 Codex 中发送：

```text
每天中午12点运行我的每日科研文献雷达，并将最终报告通过WxPusher推送到微信。
```

本地定时任务要成功执行，到点时电脑需要保持开机、联网，并且 Codex 本地运行环境可用。电脑关机后仍需推送时，应迁移到长期在线的服务器、NAS或云端任务。

## 九、更新与备份

如果使用 Git 安装，可以更新代码：

```powershell
Set-Location "$env:USERPROFILE\.codex\skills\research-paper-daily-push"
git pull
```

但更新前应先备份个人配置和历史数据，尤其是：

```text
references/research_topics.md
config/research_profile.json
data/pushed_articles.json
data/research_memory.json
```

可以把整个文件夹复制到桌面作为备份：

```powershell
$source = "$env:USERPROFILE\.codex\skills\research-paper-daily-push"
$backup = "$env:USERPROFILE\Desktop\research-paper-daily-push-backup"
Copy-Item -LiteralPath $source -Destination $backup -Recurse
```

如果目标备份文件夹已经存在，请换一个新名称，不要直接覆盖旧备份。

## 十、常见问题

### Codex 没有识别到 Skill

- 检查 `SKILL.md` 是否位于正确目录；
- 检查是否多套了一层文件夹；
- 完全关闭并重新打开 Codex；
- 在请求中明确写 `$research-paper-daily-push`。

### 显示“尚未配置研究主题”

这不是程序故障。请先让 Codex 填写研究主题和 `research_profile.json`，并把 `configured` 设为 `true`。

### PowerShell 提示找不到 python

重新安装 Python 3.10 或更高版本，并勾选“Add Python to PATH”。安装完成后重新打开 PowerShell。

### 微信没有收到测试消息

- 检查 appToken 是否以 `AT_` 开头；
- 检查 UID 是否以 `UID_` 开头；
- 设置永久环境变量后重新启动 PowerShell 和 Codex；
- 如果 WxPusher 客户端和 ClawBot 都没收到，检查 appToken、UID、网络和终端返回信息；
- 如果客户端收到而 ClawBot 没收到，在“我的 → 推送渠道”检查绑定，并在微信 ClawBot 会话中回复任意内容重新激活；
- 检查是否已经超过本次激活后的 24 小时或 10 次推送；
- 在 WxPusher 用户管理中确认 UID 对应的就是绑定 ClawBot 的接收用户。

### 当天没有推荐论文

如果检索正常但没有论文达到推荐阈值，零推荐是正常结果。不要为了凑够数量而降低质量标准。

## 最短使用清单

1. 下载并复制到 Codex Skills 目录；
2. 重启 Codex；
3. 让 Codex 配置研究方向；
4. 输入“运行我的每日科研文献雷达”；
5. 可选配置 WxPusher；
6. 需要时再创建每日定时任务。
