# ESP32-C3 8 路继电器控制系统 Spec

## Why
当前 `index.html` 仅为本地纯前端原型（状态只写入 `localStorage`，无硬件对接），没有 ESP32-C3 固件，也无法让网页 / 串口 / AI 三方统一驱动真实 8 路继电器。需要构建一套最小、可复现、协议清晰、UI 不破坏的解决方案。

## What Changes
- 新增 MicroPython 固件（运行于 ESP32-C3）：
  - GPIO1~GPIO8 直接驱动 8 路继电器
  - WiFi 在后台线程持续尝试连接已保存凭据，连接失败不影响继电器控制与串口可用性
  - 上电即开始响应继电器控制串口（不等待 WiFi）
  - 内置 HTTP JSON 控制接口，供网页调用（WiFi 联网后可用）
  - 同时启用 USB CDC 与 UART0 双串口，角色由启动脚本 `main.py` 中的常量配置（默认 `CONTROL_SERIAL = 'uart0'`：UART0 = 继电器/WiFi 控制串口，USB CDC = REPL）
  - 在控制串口完整实现 `串口通信协议` 文档中定长 4 字节协议（Header=0xA0，功能码 0x00~0x05，校验方式、返回帧全部一致）
  - 在控制串口增加 ASCII 命令 `wifi:long,pwd:longlong` 用于配置 WiFi，保存后重启
- 新增 Python MCP 服务器：
  - 启动时通过 `--mode serial|network` 指定控制通道：
    - `serial`：通过 pyserial 直连 ESP32-C3，使用 4 字节串口协议
    - `network`：通过 HTTP JSON API 调用 ESP32-C3（同一套语义）
  - 严格基于 4 字节串口协议 + WiFi ASCII 命令，不引入新协议
  - 串口模式：当串口出现异常（写入失败/读超时/端口消失）需要重新打开时，必须从配置重新加载串口参数（端口路径、波特率等）后再 open，避免使用陈旧句柄
  - 工具覆盖：单通道开/关（可选应答）、单通道查询、单通道取反、批量开/关、查询全部、设置 WiFi
- 调整 `index.html`：
  - **UI 不动**（CSS / HTML 结构 / 视觉、卡片渲染、SVG 原理图全部保留）
  - 重写 `<script>` 内逻辑：状态初始化由 `GET /api/state` 取真实值，失败回退 localStorage；卡片点击 / 全局按钮 / 通道数变更均通过 HTTP API 同步
- 新增 `requirements.txt`（MCP 服务器依赖：`pyserial`、`mcp>=2`、`requests`）
- 更新 `README.md` 给出接线、烧录、串口角色配置、MCP 启动说明

## Impact
- 受影响代码：
  - `index.html` —— 仅 `<script>` 部分重写
  - `README.md` —— 增加使用说明
- 新增目录：
  - `firmware/` —— MicroPython 源码
  - `mcp_server/` —— Python MCP 服务器源码

## ADDED Requirements

### Requirement: ESP32-C3 8 路继电器固件
系统 SHALL 在 ESP32-C3 上以 MicroPython 实现 8 路继电器控制，按以下方式映射：
- 通道 1 ~ 8 → GPIO1 ~ GPIO8
- 高电平视为「吸合」（状态 1），低电平视为「不吸合」（状态 0）

#### Scenario: 上电启动立即可控
- WHEN 设备上电
- THEN 系统立即初始化 GPIO1-8 为输出 0
  - AND 立即初始化继电器控制串口并开始响应 4 字节协议帧
  - AND 在独立线程中开始尝试连接已保存的 WiFi（无凭据则直接进入 AP 模式）
  - AND WiFi 状态不影响继电器控制串口的可用性

#### Scenario: WiFi 后台持续重试
- WHEN WiFi 连接失败或断开
- THEN 系统在后台线程继续周期性重试，间隔不短于 5 秒
  - AND 不抛出未捕获异常导致主循环退出
  - AND 已连上时切到 STA 模式并打印 IP；连不上时切到 AP 模式（AP 名 `ESP32C3-Relay`）

#### Scenario: 双串口角色由代码配置
- WHEN 系统启动
- THEN 系统按 `main.py` 中的常量 `CONTROL_SERIAL`（取值 `'uart0'` 或 `'usb_cdc'`）决定哪个串口承担继电器/WiFi 控制角色
  - 默认 `CONTROL_SERIAL = 'uart0'`：UART0 (115200) = 控制，USB CDC = REPL
  - 另一个串口承担 REPL
  - 不依赖任何物理开关或外部引脚

### Requirement: HTTP 控制 API
系统 SHALL 暴露 HTTP JSON 接口供 `index.html` 与 MCP 网络模式调用。

#### Scenario: 状态查询
- WHEN 客户端 `GET /api/state`
- THEN 返回 `{"channels":[0,0,0,0,0,0,0,0]}`，对应 8 路的 0/1 状态

#### Scenario: 单通道控制
- WHEN 客户端 `POST /api/relay` with body `{"ch":1,"state":1}`
- THEN 1 号通道被设为吸合
- AND 返回 `{"channels":[1,0,0,0,0,0,0,0]}`

#### Scenario: 批量控制
- WHEN 客户端 `POST /api/relay/all` with body `{"state":1}`
- THEN 全部通道被设为吸合
- AND 返回最新状态

#### Scenario: 通道号越界
- WHEN 客户端请求的 `ch` 不在 1~8 范围
- THEN 返回 HTTP 400 with body `{"error":"channel out of range"}`

#### Scenario: 同源策略
- WHEN 浏览器跨域访问
- THEN 响应头包含 `Access-Control-Allow-Origin: *`

### Requirement: 串口继电器协议
系统 SHALL 在继电器控制串口上完整实现 `串口通信协议` 文档中定长 4 字节协议：
- Header 固定 `0xA0`
- 帧序：Header → Addr → Func/State → Checksum，Checksum = `(前 3 字节和) & 0xFF`
- 功能码 0x00 / 0x01 不返回
- 功能码 0x02 / 0x03 改变状态后回送 4 字节状态帧
- 功能码 0x04 翻转状态后回送新状态帧
- 功能码 0x05 不改变状态，仅回送当前状态
- 通道号 `0x00` 与 `0xFF` 视为非法，丢弃该帧

### Requirement: 串口 WiFi 配置命令
系统 SHALL 在继电器控制串口接受 ASCII 文本命令 `wifi:<ssid>,pwd:<password>`：
- 保存到非易失存储
- 在重启前回显 `WIFI SAVED, REBOOTING\n`
- 触发 `machine.reset()` 进入新网络
- 命令以 `\n` 触发解析（即可在帧协议之外随时输入）

#### Scenario: 成功设置
- WHEN 在控制串口输入 `wifi:MySSID,pwd:MyPassword`
- THEN 保存凭据
  - AND 回显 `WIFI SAVED, REBOOTING\n`
  - AND 设备重启后尝试连接 `MySSID`

#### Scenario: 格式错误
- WHEN 收到以 `wifi:` 开头但不匹配 `wifi:<ssid>,pwd:<password>` 的字符串
- THEN 回显 `ERROR: bad format, expected wifi:<ssid>,pwd:<password>\n`
- AND 不重启

### Requirement: USB CDC / UART0 双串口
系统 SHALL 同时启用 USB CDC 与 UART0，二者一个为 REPL、一个为继电器/WiFi 串口，角色由 `main.py` 常量 `CONTROL_SERIAL` 决定，且无论哪个串口承担控制角色都使用同一套（串口继电器协议 + WiFi 命令）的处理逻辑。

### Requirement: Python MCP 服务器
系统 SHALL 提供 Python 实现的 MCP 服务器，AI 可通过 MCP 调用串口或 HTTP 间接控制继电器。所有工具均通过 4 字节串口协议、HTTP API 或 WiFi ASCII 命令实现，不允许设备新增其它协议。

启动参数：
- `--mode serial|network`（必填）：控制通道
- `--port <device>`（serial 模式必填）：串口设备路径
- `--baudrate <int>`（serial 模式默认 115200）
- `--host <ip>`（network 模式必填）：ESP32-C3 的 IP
- `--http-port <int>`（network 模式默认 80）

工具清单：
- `set_relay(channel: int, state: int, with_reply: bool = False) -> dict`
  - 设置通道状态，channel 范围 1-8，state 为 0/1
  - serial 模式：`with_reply=True` 时使用功能码 0x02/0x03 并解析回包；`with_reply=False` 时使用 0x00/0x01
  - network 模式：调用 `POST /api/relay`，`with_reply` 参数忽略（HTTP 自带应答）
  - 返回 `{"ok":true,"channel":N,"state":S}`
- `get_relay(channel: int) -> dict` — serial 用 0x05；network 用 `GET /api/state` 取整体后取单路，返回 `{"channel":N,"state":S}`
- `toggle_relay(channel: int) -> dict` — serial 用 0x04；network 在客户端先 `get_relay` 再 `set_relay` 取反，返回 `{"channel":N,"state":S}`
- `set_all_relays(state: int) -> dict` — serial 8 次 `set_relay(..., with_reply=False)；network 调用 `POST /api/relay/all`，返回 `{"ok":true,"state":S}`
- `get_all_relays() -> list[dict]` — serial 8 次 `get_relay`；network 一次 `GET /api/state`，返回 `[{"channel":1,"state":S},...]`
- `set_wifi(ssid: str, password: str) -> str` — serial 发送 ASCII 命令；network 不支持（HTTP 接口不暴露 WiFi 设置），调用时返回错误信息 `set_wifi not supported in network mode`

#### Scenario: 工具调用（serial）
- WHEN AI 调用 `set_relay(channel=1, state=1, with_reply=True)` 且 mode=serial
- THEN MCP 服务器发送 4 字节帧 `A0 01 03 A4`
  - AND 收到回包后返回 `{"ok":true,"channel":1,"state":1}`

#### Scenario: 工具调用（network）
- WHEN AI 调用 `set_relay(channel=1, state=1)` 且 mode=network
- THEN MCP 服务器发送 `POST /api/relay` body `{"ch":1,"state":1}`
  - AND 返回 `{"ok":true,"channel":1,"state":1}`

#### Scenario: 参数校验
- WHEN 调用 `set_relay(channel=99, state=1)`
- THEN 在发送前抛出参数异常，返回错误信息（不发起任何通讯）

#### Scenario: 串口异常重开重载配置（serial）
- WHEN serial 模式下串口写入失败 / 读超时 / 端口消失
- THEN MCP 服务器关闭旧句柄
  - AND 从启动配置重新加载 `--port` / `--baudrate`
  - AND 重新打开串口
  - AND 重开成功后下一次工具调用继续工作；重开失败则该次工具返回错误 `serial not open`

## MODIFIED Requirements

### Requirement: `index.html` `<script>` 行为
- 状态初始化：页面加载后立即 `GET /api/state`；请求失败时回退到 localStorage 现状并提示「离线模式」
- 卡片点击 → 调用 `POST /api/relay`，成功后写入 localStorage 并 `render()`；失败时回滚本地状态
- 全部 NO / NC 按钮 → 调用 `POST /api/relay/all`
- 通道数 `input` change → 维持前端缓存扩缩，但 ESP32-C3 始终为 8 路，超出 1-8 的卡片提交时按后端返回 400 忽略
- 视觉 / CSS / HTML 结构不变，仍是「继电器原理图控制面板」同款 UI

## REMOVED Requirements
无
