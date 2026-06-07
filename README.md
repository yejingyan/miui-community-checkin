# 小米社区每日签到自动化

个人自用的小米社区签到/成长值任务自动化脚本。

## 功能

- H5 主签到状态检测与尝试签到
- 微信小程序额外成长值任务 `WECHAT_CHECKIN_TASK`
- App/网页任务的低风险浏览动作
- 登录态失效时自动刷新 Cookie
- 遇到验证码、人机验证、滑块时暂停并通知人工处理

## 安全边界

本项目只用于本人账号的个人效率自动化：

- 不批量、不对外提供服务
- 不破解验证码、不绕过人机验证
- 不伪造 token
- 不上传 cookie、浏览器 profile、日志、截图等本地敏感数据

## 使用

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
./run_daily.sh
```

首次使用需要先准备本地登录态/Cookie。脚本检测到验证码或登录态失效时会退出，并保留人工处理提示。

## 入口

- `run_daily.sh`：日常执行入口
- `miui_daily_playwright.py`：主编排逻辑
- `miui_playwright_client.py`：浏览器操作与验证检测
- `miui_api_client.py`：小米社区接口封装
- `refresh_cookie_auto.py`：登录态刷新辅助
- `notify_human_needed.py`：需要人工处理时的通知辅助


## 通知配置

如需在需要人工验证时主动通知，请通过环境变量配置：

```bash
export MIUI_NOTIFY_TARGET='user-or-chat-target'
export MIUI_NOTIFY_CHANNEL='feishu'
export MIUI_NOTIFY_ACCOUNT='default'
```

不要把真实 target、账号、cookie 或 token 提交到仓库。

## 退出码

- `0`：执行成功
- `2`：需要人工验证/未签
- `3`：登录态失效
- `1`：其他错误
