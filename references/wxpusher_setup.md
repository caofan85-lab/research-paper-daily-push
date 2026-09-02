# WxPusher 微信推送配置

本项目使用 WxPusher 的标准消息 API：应用通过 `appToken` 鉴权，并通过关注用户的 `UID` 定向发送消息。Token 和 UID 只能存放在环境变量中，不要写入 JSON、Markdown、脚本、截图或 Git 提交。

如果希望消息同时出现在微信 ClawBot 中，还需要在 **WxPusher 客户端**里单独绑定并启用这个推送渠道。这里有三层关系：

```text
项目脚本
  → 使用 appToken 鉴权
  → 使用 UID 定位接收用户
  → WxPusher 创建并分发消息
      ├─ WxPusher 客户端
      └─ 已绑定且当前已激活的微信 ClawBot
```

因此，“WxPusher 客户端收到了”只证明 `appToken + UID` 基本正确，并不等于 ClawBot 已绑定、已激活或仍在可推送期限内。ClawBot 绑定不会产生新的项目环境变量，也不需要修改本项目的发送 API。

官方入口：

- 管理后台：<https://wxpusher.zjiecode.com/admin/>
- WxPusher 客户端下载：<https://wxpusher.zjiecode.com/download/>
- 标准推送 API：<https://wxpusher.zjiecode.com/docs/api-reference.html>
- 完整文档：<https://wxpusher.zjiecode.com/docs/>
- 官方文档源码（含微信 ClawBot 说明）：<https://github.com/wxpusher/wxpusher-docs>

## 1. 创建应用并取得 appToken

1. 用微信扫码登录 WxPusher 管理后台。
2. 进入“应用管理”，创建应用；应用名称可填写“科研文献雷达”。
3. 联系方式和推送内容说明按实际用途填写，例如“每日科研论文检索与中文解读”。个人使用通常不需要配置事件回调地址。
4. 创建成功后进入应用的 `appToken` 页面，复制以 `AT_` 开头的完整值。

`appToken` 相当于该推送应用的发送密钥。若它曾出现在公开仓库、公开截图或聊天分享中，应在后台重新生成或更换，然后更新环境变量。

## 2. 关注应用并取得 UID

1. 在该应用的管理页面打开“关注应用”二维码或关注链接。
2. 使用需要接收消息的用户扫码，完成关注和激活。
3. 回到该应用的“用户管理”页面，找到刚关注的用户，复制以 `UID_` 开头的完整 UID。

UID 属于接收者身份，不是 `appToken`。不要填写昵称、微信号、ClawBot 名称或其他应用的 UID。多人接收时，可在 `WXPUSHER_UID` 中用英文逗号或分号分隔多个 UID。

## 3. 在 WxPusher 客户端中绑定微信 ClawBot

这一步是“把 WxPusher 消息转送到微信 ClawBot”的关键，不能只在网页管理后台完成。

### 第一步：准备同一个接收用户

1. 从 [WxPusher 官方下载页](https://wxpusher.zjiecode.com/download/)安装或更新 WxPusher 客户端。
2. 登录 WxPusher 客户端，确认这是第 2 节中关注应用、取得目标 `UID` 的同一个接收用户。
3. 先在客户端中确认能够看到该应用，避免把 A 用户的 UID 与 B 用户绑定的 ClawBot 混在一起。

> 项目发送时只知道 UID，不知道你的微信昵称或 ClawBot 名称。UID 所属用户与绑定 ClawBot 的用户必须一致。

### 第二步：打开 ClawBot 绑定入口

在最新版 WxPusher 客户端中依次进入：

```text
我的 → 推送渠道 → 绑定微信 ClawBot
```

按照客户端页面的提示完成微信侧授权或绑定。不同客户端版本的按钮文字可能略有差异，应以当前页面提示为准。完成后返回“推送渠道”页面，确认微信 ClawBot 显示为已绑定或已启用。

### 第三步：在微信会话中激活

1. 打开微信中的 ClawBot 会话。
2. 主动回复任意内容，例如“激活”。
3. 返回 WxPusher 客户端，确认渠道没有显示待激活、已过期或连接失败。

根据 WxPusher 当前官方说明，每次激活后最多可在 24 小时内接收 10 次 ClawBot 推送；超过 24 小时或用完次数后，需要在 ClawBot 会话中再次回复任意内容来重新激活。这个限制独立于 WxPusher API 本身的调用限制，反复发送测试消息也可能消耗次数。规则可能随平台调整，请以 [WxPusher 官方文档](https://wxpusher.zjiecode.com/docs/)的最新说明为准。

这意味着 ClawBot 更适合作为微信内的提醒渠道，而不是完全无人值守的永久通道。若希望每天自动推送，建议同时保留 WxPusher 客户端作为接收兜底，并在 ClawBot 到期后按提示重新激活。本项目无法代替用户在微信中回复消息，也无法通过代码绕过该限制。

### 第四步：确认四个必要条件

正式测试前逐项检查：

- `appToken` 来自当前 WxPusher 应用，且仍然有效；
- `UID` 来自已经关注该应用的目标接收用户；
- 该 UID 所属用户已在 WxPusher 客户端绑定并启用微信 ClawBot；
- 微信 ClawBot 当前处于已激活状态，且未超过 24 小时或 10 次推送限制。

四项都满足后，项目不需要额外的 ClawBot 参数：继续配置 `WXPUSHER_APP_TOKEN` 和 `WXPUSHER_UID` 即可。

## 4. Windows 新手推荐：从剪贴板自动读取

不要把真实 Token 或 UID 直接写进命令。手动粘贴时容易复制到多余文字、漏掉字符，真实凭据还可能进入 PowerShell 命令历史。

下面的方法会在脚本已经开始等待后再读取剪贴板。它只显示“是否存在、前缀是否正确、长度和格式是否合理”，不会在终端显示真实 Token 或 UID。只有两项检查都通过后才会一起保存，因此 UID 复制错误时也不会覆盖原有 Token。

### 第一步：打开正确的 PowerShell 目录

从开始菜单搜索并打开“PowerShell”，然后运行：

```powershell
Set-Location "$env:USERPROFILE\.codex\skills\research-paper-daily-push"
```

不需要使用 `Win + R`。

### 第二步：先复制下面整段配置程序

把下面整个代码块复制到 PowerShell，按一次 Enter。程序出现“请复制 appToken”后会暂停等待：

```powershell
& {
    $newToken = ""
    $newUid = ""
    try {
        Write-Host "第 1 步：打开 WxPusher 当前应用的 appToken 页面。" -ForegroundColor Cyan
        Write-Host "请复制 appToken：只复制 AT_ 开头的完整值，不要复制标签、引号或整行网页。"
        Read-Host "复制完成后回到此窗口，按 Enter 让程序读取剪贴板" | Out-Null

        $newToken = ([string](Get-Clipboard -Raw)).Trim()
        $tokenConfigured = -not [string]::IsNullOrWhiteSpace($newToken)
        $tokenPrefixCorrect = $newToken.StartsWith("AT_")
        $tokenFormatCorrect = $newToken -match '^AT_[A-Za-z0-9]+$'
        $tokenLengthReasonable = $newToken.Length -ge 20 -and $newToken.Length -le 100

        [pscustomobject]@{
            Item = "appToken"
            Configured = $tokenConfigured
            PrefixCorrect = $tokenPrefixCorrect
            FormatCorrect = $tokenFormatCorrect
            Length = $newToken.Length
        } | Format-Table -AutoSize

        if (-not ($tokenConfigured -and $tokenPrefixCorrect -and $tokenFormatCorrect -and $tokenLengthReasonable)) {
            Write-Host "appToken 检查未通过，本次没有保存任何配置。请重新从 appToken 页面复制。" -ForegroundColor Red
            return
        }

        Write-Host "第 2 步：进入该应用的用户管理页面。" -ForegroundColor Cyan
        Write-Host "请复制 UID：只复制目标用户 UID_ 开头的完整值。"
        Read-Host "复制完成后回到此窗口，按 Enter 让程序读取剪贴板" | Out-Null

        $newUid = ([string](Get-Clipboard -Raw)).Trim()
        $uidConfigured = -not [string]::IsNullOrWhiteSpace($newUid)
        $uidPrefixCorrect = $newUid.StartsWith("UID_")
        $uidFormatCorrect = $newUid -match '^UID_[A-Za-z0-9]+$'
        $uidLengthReasonable = $newUid.Length -ge 20 -and $newUid.Length -le 100

        [pscustomobject]@{
            Item = "UID"
            Configured = $uidConfigured
            PrefixCorrect = $uidPrefixCorrect
            FormatCorrect = $uidFormatCorrect
            Length = $newUid.Length
        } | Format-Table -AutoSize

        if (-not ($uidConfigured -and $uidPrefixCorrect -and $uidFormatCorrect -and $uidLengthReasonable)) {
            Write-Host "UID 检查未通过，本次没有保存任何配置。请重新从用户管理页面复制。" -ForegroundColor Red
            return
        }

        [Environment]::SetEnvironmentVariable("WXPUSHER_APP_TOKEN", $newToken, "User")
        [Environment]::SetEnvironmentVariable("WXPUSHER_UID", $newUid, "User")
        $env:WXPUSHER_APP_TOKEN = $newToken
        $env:WXPUSHER_UID = $newUid

        Write-Host "配置已保存到当前 Windows 用户，并已加载到这个 PowerShell 窗口。" -ForegroundColor Green
        Write-Host "程序没有显示或记录真实 appToken 和 UID。"
    }
    finally {
        try { Set-Clipboard -Value "" } catch {}
        Remove-Variable -Name newToken,newUid,tokenConfigured,tokenPrefixCorrect,tokenFormatCorrect,tokenLengthReasonable,uidConfigured,uidPrefixCorrect,uidFormatCorrect,uidLengthReasonable -ErrorAction SilentlyContinue
    }
}
```

### 第三步：按照两次提示操作

第一次暂停时：

1. 切换到 WxPusher 后台；
2. 点击左侧“appToken”；
3. 只复制 `AT_` 开头的完整值；
4. 回到 PowerShell；
5. 不要粘贴，直接按 Enter。

第二次暂停时：

1. 切换到“用户管理”；
2. 找到需要接收消息的微信用户；
3. 只复制 `UID_` 开头的完整值；
4. 回到 PowerShell；
5. 不要粘贴，直接按 Enter。

这里的关键是“复制后直接按 Enter”，不要再按 `Ctrl + V`。程序会自动调用 `Get-Clipboard -Raw` 读取剪贴板。

### 第四步：看懂检查结果

正常结果类似下面这样，长度不要求与示例完全相同：

```text
Item     Configured PrefixCorrect FormatCorrect Length
----     ---------- ------------- ------------- ------
appToken       True          True          True     35

Item Configured PrefixCorrect FormatCorrect Length
---- ---------- ------------- ------------- ------
UID        True          True          True     35
```

判断标准：

- `Configured=True`：剪贴板不是空的；
- `PrefixCorrect=True`：Token 为 `AT_` 开头，UID 为 `UID_` 开头；
- `FormatCorrect=True`：没有复制进空格、引号、换行或其他网页文字；
- `Length`：只用于发现明显错误，不需要手动照抄某个固定长度。

只要任一项为 `False`，程序就不会保存。重新运行整个代码块，再从正确页面复制即可。不要为了让检查通过而手动修改看不懂的字符串。

### 第五步：立即检查项目是否读到配置

仍在同一个 PowerShell 窗口中运行：

```powershell
python scripts\push_wechat.py --provider wxpusher --check-config
```

预期结果：

```text
配置有效：通知渠道=wxpusher；接收者数量=1。未输出任何凭据。
```

之后新打开的 PowerShell 和 Codex 也会读取用户级环境变量。如果已经打开 Codex，建议完全关闭后重新启动一次。

### 剪贴板安全提醒

配置程序结束时会清空当前剪贴板，但 Windows 剪贴板历史或第三方剪贴板工具仍可能保留旧内容。如果启用了剪贴板历史，可在“设置 → 系统 → 剪贴板”中清除历史记录。共享电脑上不建议长期保存个人推送凭据。

## 5. 其他系统或手动配置

### Windows PowerShell：仅当前窗口

只有无法使用剪贴板方法时才考虑手动输入。下面的示例占位符不能原样使用：

```powershell
$env:WXPUSHER_APP_TOKEN = "AT_替换为完整Token"
$env:WXPUSHER_UID = "UID_替换为完整UID"
```

该方式关闭 PowerShell 后失效。

### macOS / Linux：当前终端

```bash
export WXPUSHER_APP_TOKEN='AT_替换为完整Token'
export WXPUSHER_UID='UID_替换为完整UID'
```

长期运行时，应通过服务器、容器或任务调度器的密钥/环境变量功能注入凭据，不要把真实值写入仓库。

## 6. 本地检查与真实测试

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

### 分两处验收

发送后不要只看终端，应分别确认：

1. WxPusher 客户端是否收到“WxPusher 配置测试”；
2. 微信 ClawBot 会话是否收到同一条消息。

可以根据结果快速定位：

| 测试结果 | 更可能的问题 | 下一步 |
| --- | --- | --- |
| 两处都收到 | 配置完成 | 再运行一次每日报告推送即可 |
| 两处都没收到 | appToken、UID、网络或 API 配置 | 先运行 `--check-config`，再检查终端返回信息 |
| 客户端收到，ClawBot 没收到 | ClawBot 绑定、激活状态、次数或用户对应关系 | 不要先更换 Token；回到“我的 → 推送渠道”检查，并在微信会话中回复任意内容重新激活 |
| 终端成功，但稍后才收到 | 平台正在异步分发 | 稍等后再检查，不要连续重复测试 |

这里所说的“实时推送”是指消息任务创建后由 WxPusher 尽快异步分发，不是严格的毫秒级实时保证。业务码 `1000` 代表发送任务已创建，不单独证明微信端已经送达。

## 7. 推送每日报告

完成论文筛选和报告生成后执行：

```powershell
python scripts/run_daily.py deliver --reviewed reviewed_articles.json --report daily-report.md --provider wxpusher
```

也可以使用 `--provider auto`；当 WxPusher 的两个环境变量均存在时，自动模式会优先选择 WxPusher。只有推送成功后，交付阶段才应提交去重历史和研究记忆。

定时任务的运行账户也必须能读取这两个环境变量。交互式 PowerShell 中测试成功，并不必然代表 Windows 任务计划程序、服务器服务或容器已经继承同一套环境变量。

每日报告较长时，项目可能把内容拆成多个消息分段。每个分段都可能占用一次渠道推送次数，因此应减少无意义的重复测试；若 ClawBot 当天突然停止接收，先检查激活期限和剩余次数。

## 8. 常见问题

### 显示“微信推送尚未配置”

- 检查两个变量是否都已设置。
- 若刚使用用户级永久变量，重启 PowerShell 和 Codex。
- 确认定时任务运行账户与设置变量的 Windows 用户一致。

### 显示 Token 或 UID 前缀错误

- `WXPUSHER_APP_TOKEN` 必须使用当前应用中以 `AT_` 开头的 appToken。
- `WXPUSHER_UID` 必须使用关注当前应用后获得、以 `UID_` 开头的 UID。
- 不要把关注二维码链接、ClawBot 名称、昵称、SPT 或其他应用的 UID 填入这些变量。
- 推荐重新运行“从剪贴板自动读取”代码块，不要在旧字符串上手动增删字符。

### API 返回 `1001 appToken错误`

- 重新从当前应用的 appToken 页面完整复制，不要复制输入框示例或旧 Token。
- 去除首尾空格、引号和换行。
- 如果重新生成过 Token，旧 Token 会失效，需要同步更新环境变量并重启运行环境。
- 如果终端曾显示长度明显异常，例如复制出一百多个字符，通常是复制了整段网页文字；剪贴板检查会拒绝保存这种值。

### WxPusher客户端中收到，但微信 ClawBot 没收到

- 这通常说明 appToken、UID 和项目发送路径基本可用，但 ClawBot 这一接收渠道尚未就绪；这是根据“双端测试结果”作出的排查判断。
- 在 WxPusher 客户端打开“我的 → 推送渠道”，确认微信 ClawBot 已绑定并启用。
- 打开微信 ClawBot 会话，回复任意内容重新激活，再发送一次测试消息。
- 检查是否已经超过当前激活后的 24 小时，或已经使用 10 次推送。
- 在管理后台“用户管理”中核对 UID，并确认该 UID 所属用户就是绑定 ClawBot 的用户。
- 不要因为 ClawBot 单独未收到就反复更换 appToken；API 成功仅表示平台接受了发送任务。

### ClawBot 显示“暂无法链接 openClaw”或连接异常

1. 先确认同一条测试消息能否在 WxPusher 客户端收到；若能收到，项目的标准推送配置通常不需要重做。
2. 在 WxPusher 客户端打开“我的 → 推送渠道”检查状态；若当前版本提供解除绑定或重新绑定入口，按照页面提示重新完成绑定。
3. 重新打开微信 ClawBot 会话并回复任意内容完成激活。
4. 等待片刻后只发送一次测试消息，分别检查客户端和微信会话。
5. 若仍异常，保留 WxPusher 客户端接收渠道，并通过 WxPusher 官方文档或客服核对当前 ClawBot 服务状态。

“openClaw”相关提示属于 ClawBot 渠道的连接或激活状态，不应把网页后台的 appToken、关注二维码或 UID 互相替换。项目也无法从 API 端自动完成微信授权。

### ClawBot 原来能收到，后来停止接收

- 在 ClawBot 会话中回复任意内容，重新开始一次有效激活。
- 检查是否超过每次激活后的 24 小时或 10 次推送限制。
- 长报告可能拆成多段；测试和报告分段都可能更快消耗渠道次数。
- 确认 WxPusher 客户端仍然可以接收，以区分 API 问题和 ClawBot 渠道问题。

### 定时运行没有收到

- 电脑关机或休眠时，本地定时任务无法执行；需使用长期在线的服务器、NAS 或云端任务。
- 检查调度器日志，以及调度器账户是否能读取环境变量。
- 确认服务器能访问 `https://wxpusher.zjiecode.com`。

### 安全处理

- 命令输出、状态 JSON 和报告不得包含真实 Token 或 UID。
- `.env` 已被 Git 忽略，但仍应在提交前运行敏感信息检查。
- 凭据一旦公开，立即在 WxPusher 后台更换，不要仅删除历史文件。
