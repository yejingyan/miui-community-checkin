# 小米社区 H5 主签到自动化证据链

更新时间：2026-05-05

## 结论

当前 H5 主签到入口没有发现可绕过 `miverify/GeeTest` 的第二条官方接口路径。

前端源码与低风险 API 探测共同显示：

1. H5 主签到页面唯一签到动作是：
   `initMiverify -> startVerify(scene="GROW_UP_CHECKIN") -> onSuccess(flag) -> checkinV2({ token: flag })`
2. `checkinV2` 裸调用或空/假 token 调用会返回：
   `{"status":640,"message":"人机校验失败"}`。
3. `api/community/user/task/start|end|acquire` 是普通任务系统状态机，用于“开始任务/进行中/领取奖励”，不是 H5 主签到。
4. `addCommunityGrowUpPointByActionV2` 对应“小米社区微信小程序签到获成长值”额外任务，不能等同于 H5 主签到。
5. `getCheckinPageCakeList` 中“每日签到”任务项 `jumpText=""`、`jumpUrl=""`，说明按钮逻辑在当前 H5 页面内部完成，而不是跳转到另一个任务接口。
6. `getRepairCost` 返回补签成本；`repairCheckIn` 需要消耗金币，不能自动调用。

## 前端源码证据

前端目录：`/tmp/miui_frontend`

关键文件：

- `/tmp/miui_frontend/1109.fac17325.chunk.js`：H5 签到页组件
- `/tmp/miui_frontend/6995.4dbe04b4.chunk.js`：API 封装定义
- `/tmp/miui_frontend/miverify.sdk.js`：小米 miverify SDK
- `/tmp/miui_frontend/9117.fcd47f50.chunk.js`：普通任务组件

### 主签到页调用链

`1109.fac17325.chunk.js` 中：

```js
window.initMiverify({
  k: "3dc42a135a8d45118034d1ab68213073",
  errorAction: true,
  timeout: 10000,
  onSuccess(e) {
    onSuccess(e?.flag)
  }
})

startVerify: e => {
  u.current.start({ a: scene, activeVerify: e, uid: C || "未知" })
}

me = async e => {
  const r = await h.default.checkIn.checkinV2({ token: e })
}

he = L({
  onSuccess: me,
  scene: "GROW_UP_CHECKIN"
})

onClick: async () => {
  if (G || oe || le !== ee || de) return
  const { popLimit: e } = B
  ae
    ? k.qX
      ? e && he.getCloseCount() >= e
        ? toast("校验失败次数过多，今日签到失败")
        : (fe(true), he.startVerify(!!e))
      : toast(`${H.o5K}参与签到`)
    : toast("请使用最新版小米社区app参与签到")
}
```

含义：

- 非 App 环境：提示“请使用最新版小米社区app参与签到”。
- App 能力不足：提示需要 App 参与签到。
- App 环境满足：调用 `he.startVerify(...)`，即启动 `miverify`。
- `miverify` 成功后才拿 `flag` 调 `checkinV2({token: flag})`。

### API 封装定义

`6995.4dbe04b4.chunk.js` 中：

```js
checkIn: {
  getUserCheckinInfo: F("mtop/planet/vip/user/getUserCheckinInfo", "GET"),
  getUserCheckinInfoV2: F("mtop/planet/vip/user/getUserCheckinInfoV2", "GET"),
  checkin: F("mtop/planet/vip/user/checkin", "POST"),
  getCheckinPageCakeList: F("mtop/planet/vip/member/getCheckinPageCakeList", "GET"),
  checkinV2: F("mtop/planet/vip/user/checkinV2", "POST"),
  getRepairCost: F("mtop/planet/vip/user/getRepairCost", "GET"),
  repairCheckIn: F("mtop/planet/vip/user/repairCheckIn", "POST")
}
```

`checkinV2` 没有配置 `isNotCheckCode:true`，因此 `status=640` 会被前端错误处理；这与裸 API 调用返回“人机校验失败”一致。

### 普通任务系统不是主签到

`6995.4dbe04b4.chunk.js` 仅定义：

```js
startTask: F("api/community/user/task/start", "POST", { isNotCheckCode: true, resHasEntity: false }),
endTask: F("api/community/user/task/end", "POST", { isNotCheckCode: true, resHasEntity: false }),
receiveCoin: F("api/community/user/task/acquire", "POST", { isNotCheckCode: true, resHasEntity: false })
```

`9117.fcd47f50.chunk.js` 调用逻辑为：

- `stat === 0`：`startTask({taskId})`
- `stat === 1`：执行/打开任务动作，然后 `endTask({taskId})`
- `stat === 2`：`receiveCoin({taskId})`

这是普通任务状态机，不是签到页的 `GROW_UP_CHECKIN -> checkinV2` 链路。

## 全量计数证据

脚本：临时命令对 `/tmp/miui_frontend/*.js` 做字符串计数。

结果：

```text
checkinV2:
  1109.fac17325.chunk.js 1
  6995.4dbe04b4.chunk.js 2
  TOTAL 3

getUserCheckinInfoV2:
  1109.fac17325.chunk.js 1
  6995.4dbe04b4.chunk.js 2
  TOTAL 3

GROW_UP_CHECKIN:
  1109.fac17325.chunk.js 1
  TOTAL 1

addCommunityGrowUpPointByActionV2:
  6995.4dbe04b4.chunk.js 1
  TOTAL 1

api/community/user/task/start:
  6995.4dbe04b4.chunk.js 1
  TOTAL 1

api/community/user/task/end:
  6995.4dbe04b4.chunk.js 1
  TOTAL 1

api/community/user/task/acquire:
  6995.4dbe04b4.chunk.js 1
  TOTAL 1
```

说明：

- `GROW_UP_CHECKIN` 全前端只在主签到组件中出现一次。
- `checkinV2` 只出现在 API 定义与主按钮成功回调。
- 额外成长值接口、普通任务接口没有进入主签到链。

## API 探测证据

运行脚本：`probe_official_task_actions.py`

关键响应：

### `getUserCheckinInfoV2`

```json
{
  "message": "success",
  "entity": {
    "checkinInfoList": [
      "签到成长值随机，连续签到有惊喜~",
      "双重惊喜：每天可在小米社区微信小程序额外签到一次",
      "补签规则：每180天可消耗金币补签一次"
    ],
    "continueCheckInDays": 1,
    "continueCheckin7DaysDetail": [0,1,-1,-1,-1,-1,-1],
    "checkin7DaysDetail": [2,0,-1,-1,-1,-1,-1],
    "popLimit": 3
  },
  "status": 200
}
```

### `getCheckinPageCakeList`

“每日签到”项：

```text
title = '每日签到'
jumpText = ''
jumpUrl = ''
desc = '签到奖励随机，以实际获得为准'
```

“小米社区微信小程序签到获成长值”项：

```text
title = '小米社区微信小程序签到获成长值'
jumpText = '去微信'
jumpUrl = 'weapp://pages/mine/index?ref=usercenter'
desc = '升级至最新版本可跳转'
```

### 成长记录

`getGrowUpPageData` 中当天记录包含：

```text
浏览帖子 +1 2026/05/05
小程序签到 +3 2026/05/05
```

没有当天“每日签到”记录。历史记录里可见“每日签到”，说明它是独立于“小程序签到”的另一类成长记录。

## 当前脚本状态

固定目录：`/root/.openclaw/workspace/runtime/miui-community-daily`

固定调用链：

```text
run_daily.sh -> python3 checkin_notify.py -> checkin_v2.py
```

当前脚本只能：

- 自动查询签到状态。
- 自动尝试微信小程序额外成长值任务。
- 自动触发/输出 `miverify` 验证链接。
- 在配置外部 GeeTest 结果源时，尝试用合法 provider 的 `validate/challenge` 换 token 后调用 `checkinV2`。

当前脚本不能：

- 自行破解或伪造 `miverify/GeeTest` token。
- 在没有合法 `miverify flag` 的情况下完成 H5 主签到。
- 将小程序额外任务冒充成 H5 主签到。

## 对外准确状态

- “小程序额外签到/成长值 +3”：已自动处理过，今日成长记录存在。
- “H5 主签到/每日签到”：当前仍未自动完成，官方 H5 前端要求 `miverify/GeeTest` 成功后的 `flag` 才能调用 `checkinV2`。
