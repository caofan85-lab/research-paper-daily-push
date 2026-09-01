# WxPusher 微信推送配置

本项目使用 WxPusher 的标准消息 API：应用通过 `appToken` 鉴权，并通过关注用户的 `UID` 定向发送消息。Token 和 UID 只能存放在环境变量中，不要写入 JSON、Markdown、脚本、截图或 Git 提交。

官方入口：

- 管理后台：<https://wxpusher.zjiecode.com/admin/>
- 标准推送 API：<https://wxpusher.zjiecode.com/docs/api-reference.html>
- 完整文档：<https://wxpusher.zjiecode.com/docs/>

## 1. 创建应用并取得 appToken

1. 用微信扫码登录 WxPusher 管理后台。
2. 进入“应用管理”，创建应用；应用名称可填写“科研文献雷达”。
3. 联系方式和推送内容说明按实际用途填写，例如“每日科研论文检索与中文解读”。个人使用通常不需要配置事件回调地址。
4. 创建成功后进入应用的 `appToken` 页面，复制以 `AT_` 开头的完整值。

`appToken` 相当于该推送应用的发送密钥。若它曾出现在公开仓库、公开截图或聊天分享中，应在后台重新生成或更换，然后更新环境变量。

## 2. 关注应用并取得 UID

1. 在该应用的管理页面打开“关注应用”二维码或关注链接。
2. 使用需要接收消息的微信扫码，完成关注和激活。若使用微信 ClawBot，确认它已显示连接或激活成功。
3. 回到该应用的“用户管理”页面，找到刚关注的用户，复制以 `UID_` 开头的完整 UID。

UID 属于接收者身份，不是 `appToken`。不要填写昵称、微信号、ClawBot 名称或其他应用的 UID。多人接收时，可在 `WXPUSHER_UID` 中用英文逗号或分号分隔多个 UID。

## 3. 设置环境变量

### Windows PowerShell：仅当前窗口

```powershell
$env:WXPUSHER_APP_TOKEN = "AT_替换为完整Token"
$env:WXPUSHER_UID = "UID_替换为完整UID"
```

该方式关闭 PowerShell 后失效，但适合首次测试。

### Windows PowerShell：永久保存到当前用户

```powershell
$newToken = Read-Host "粘贴完整 appToken"
$newUid = Read-Host "粘贴完整 UID"
[Environment]::SetEnvironmentVariable("WXPUSHER_APP_TOKEN", $newToken.Trim(), "User")
[Environment]::SetEnvironmentVariable("WXPUSHER_UID", $newUid.Trim(), "User")
Remove-Variable newToken, newUid
```

设置后必须完全关闭并重新打开 PowerShell 和 Codex，已经运行的程序不会自动取得新环境变量。无需使用 `Win + R`。

### macOS / Linux：当前终端

```bash
export WXPUSHER_APP_TOKEN='AT_替换为完整Token'
export WXPUSHER_UID='UID_替换为完整UID'
```

长期运行时，应通过服务器、容器或任务调度器的密钥/环境变量功能注入凭据，不要把真实值写入仓库。

## 4. 本地检查与真实测试

先进行本地检查；这一步不会联网发送，也不会显示凭据内容：

```powershell
python scripts/push_wechat.py --provider wxpusher --check-config
```

预期结果类似：

```text
配置有效：通知渠道=wxpusher；接收者数量=1。未输出任何凭据。
```

然后明确执行真实测试推送：

```powershell
python scripts/push_wechat.py --provider wxpusher --test-message
```

成功时终端显示：

```text
wxpusher 发送完成；共 1 个消息分段。
```

WxPusher 返回业务码 `1000` 表示发送任务创建成功；消息仍由平台异步分发，因此还应在微信或 ClawBot 中确认实际收到消息。

## 5. 推送每日报告

完成论文筛选和报告生成后执行：

```powershell
python scripts/run_daily.py deliver --reviewed reviewed_articles.json --report daily-report.md --provider wxpusher
```

也可以使用 `--provider auto`；当 WxPusher 的两个环境变量均存在时，自动模式会优先选择 WxPusher。只有推送成功后，交付阶段才应提交去重历史和研究记忆。

定时任务的运行账户也必须能读取这两个环境变量。交互式 PowerShell 中测试成功，并不必然代表 Windows 任务计划程序、服务器服务或容器已经继承同一套环境变量。

## 6. 常见问题

### 显示“微信推送尚未配置”

- 检查两个变量是否都已设置。
- 若刚使用用户级永久变量，重启 PowerShell 和 Codex。
- 确认定时任务运行账户与设置变量的 Windows 用户一致。

### 显示 Token 或 UID 前缀错误

- `WXPUSHER_APP_TOKEN` 必须使用当前应用中以 `AT_` 开头的 appToken。
- `WXPUSHER_UID` 必须使用关注当前应用后获得、以 `UID_` 开头的 UID。
- 不要把关注二维码链接、ClawBot 名称、昵称、SPT 或其他应用的 UID 填入这些变量。

### API 返回 `1001 appToken错误`

- 重新从当前应用的 appToken 页面完整复制，不要复制输入框示例或旧 Token。
- 去除首尾空格、引号和换行。
- 如果重新生成过 Token，旧 Token 会失效，需要同步更新环境变量并重启运行环境。

### WxPusher客户端中收到，但微信 ClawBot 没收到

- 确认微信端 ClawBot 已完成连接和激活，而不只是关注应用。
- 在“用户管理”核对 UID 对应的确实是目标微信用户。
- 重新执行测试消息；API 成功仅表示平台已接受发送任务。

### 定时运行没有收到

- 电脑关机或休眠时，本地定时任务无法执行；需使用长期在线的服务器、NAS 或云端任务。
- 检查调度器日志，以及调度器账户是否能读取环境变量。
- 确认服务器能访问 `https://wxpusher.zjiecode.com`。

### 安全处理

- 命令输出、状态 JSON 和报告不得包含真实 Token 或 UID。
- `.env` 已被 Git 忽略，但仍应在提交前运行敏感信息检查。
- 凭据一旦公开，立即在 WxPusher 后台更换，不要仅删除历史文件。
