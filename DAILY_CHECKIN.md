# 小米社区每日签到定时链路

## 当前入口

固定工作目录：

```bash
/root/.openclaw/workspace/runtime/miui-community-daily
```

统一入口：

```bash
./run_daily.sh
```

实际调用链：

```text
run_daily.sh
  -> python3 miui_daily_orchestrator.py
       -> checkin_v2.py
       -> check_status.py
```

## 执行内容

### 1. H5 主签到

`checkin_v2.py` 会先调用官方：

```text
mtop/planet/vip/user/getUserCheckinInfoV2
```

如果今天已签：

- 输出连续签到天数。
- 清理旧的 `miui_verify_pending.json`。
- 退出 0。

如果今天未签：

- 尝试走官方 `miverify` 数据接口拿 `GROW_UP_CHECKIN` token。
- 拿到 token 才调用：

```text
mtop/planet/vip/user/checkinV2
```

如果小米返回二级 `GeeTest`：

- 不裸调 `checkinV2`。
- 不伪造/破解 token。
- 保存本次 `MIUI_VERIFY_URL` 到 `miui_verify_pending.json`。
- 可选：如果配置了 `geetest_bridge.json`，用合法 provider 返回的 `validate/challenge` 换小米 token。

### 2. 微信小程序额外成长值任务

当 H5 主签到被 `miverify/GeeTest` 卡住时，`checkin_v2.py` 会继续尝试官方额外任务：

```text
mtop/planet/vip/member/addCommunityGrowUpPointByActionV2
action=WECHAT_CHECKIN_TASK
```

注意：这是“小米社区微信小程序签到获成长值”，不是 H5 主签到。

### 3. 状态复查 / pending 清理

`miui_daily_orchestrator.py` 最后会运行：

```bash
python3 check_status.py
```

作用：

- 只读复查 `getUserCheckinInfoV2`。
- 如果老板手动完成了 H5 验证，自动检测已签并清理 pending。
- 避免旧验证链接长期残留。

## 定时任务

当前 crontab 应保持：

```cron
5 8 * * * /root/.openclaw/workspace/runtime/miui-community-daily/run_daily.sh >> /root/.openclaw/workspace/runtime/miui-community-daily/logs/daily.log 2>&1
```

语义：每天北京时间 08:05 执行。

## 退出码策略

`miui_daily_orchestrator.py`：

- `0`：已签 / H5 需要人工验证但已保存 pending / 小程序额外任务已处理 / 状态复查正常。
- 非 0：真实脚本错误，例如接口异常、Cookie 失效、代码异常。

这可以避免 cron 把“需要人工验证”误判成系统失败。

## 验证命令

```bash
cd /root/.openclaw/workspace/runtime/miui-community-daily
./.venv/bin/python test_miui_daily_orchestrator.py
./.venv/bin/python miui_daily_orchestrator.py
```

## 今日已验证状态（2026-05-05）

老板手动完成 H5 人机验证后，官方状态为：

```text
checkin7DaysDetail=[2,5,-1,-1,-1,-1,-1]
continueCheckInDays=2
```

说明今天 H5 主签到已完成，连续签到 2 天。
