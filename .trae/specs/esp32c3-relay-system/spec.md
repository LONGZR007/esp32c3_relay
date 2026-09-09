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
系统 SHALL 提供 Python 实现的 MCP 服务器，AI 可通过 MCP 调用串口或 HTTP 间接控制继电器。所有工具均通过 4 字节串口协议、HTTP API 或 WiFi ASCII 命令实现，不允许设备新增其它协议。后端（serial/network）由 `config.json` 的 `mode` 字段决定，串口参数与设备映射也从 `config.json` 读取（`RELAY_PORT` 环境变量覆盖串口端口）。

启动参数（控制 MCP 服务器自身的传输，与后端 mode 正交）：
- `--config <path>`（默认同目录 `config.json`）：配置文件路径，含 mode/port/baudrate/host/http_port/devices
- `--transport stdio|sse|streamable-http`（默认 stdio）：MCP 服务器自身的传输
- `--host <ip>`（sse/streamable-http 默认 127.0.0.1）：MCP 服务器监听地址
- `--port <int>`（sse/streamable-http 默认 8000）：MCP 服务器监听端口，streamable-http 端点为 `http://<host>:<port>/mcp`
- `--stateless-http / --no-stateless-http`（默认开）：streamable-http 无状态模式，不要求客户端回传 session id；`--no-stateless-http` 改为有状态

config.json 字段：
- `mode: serial|network` — 后端控制通道
- `port` / `baudrate` — serial 模式串口设备与波特率（默认 9600，与串口通信协议文档一致；`RELAY_PORT` 环境变量覆盖 port）
- `host` / `http_port` — network 模式 ESP32-C3 的 IP 与 HTTP 端口（默认 80）
- `devices[]` — 设备映射，每项 `{name, channel 1-8, active_high, note}`；`active_high=true` 表示"上电=继电器吸合(GPIO高)"，`false` 表示"上电=继电器断开(低电平触发)"

工具清单（三层语义）：
- 设备层（面向上下电语义，推荐 AI 优先使用）：
  - `list_devices() -> list[dict]` — 遍历 config 的 devices 逐路 query，返回 `[{device, channel, active_high, note, relay_state, relay_on, powered, error}]`；某路无响应时该路 `powered=null` 并附 `error`，不影响其它路
  - `power_on(device: str) -> dict` — 按 active_high 换算后调 `turn_on_ack`/`turn_off_ack`，返回 `{device, channel, relay_state, relay_on, powered, note}`
  - `power_off(device: str) -> dict` — 同上反向
  - `power_toggle(device: str) -> dict` — 调 `toggle`，返回翻转后状态
  - `power_status(device: str) -> dict` — 调 `query`，返回当前状态
  - `device` 可传设备名（如 `relay_1`）或通道号字符串（如 `"1"`）
- 继电器层（原始通道控制）：
  - `relay_control(channel: int, action: str) -> dict` — `action ∈ {on, off, toggle, query}`，serial 用 0x03/0x02/0x04/0x05；network 用 `POST /api/relay` 或 `GET /api/state`，返回 `{channel, relay_state, relay_on}`
- 资源管理：
  - `release_serial() -> dict` — 关闭底层连接（串口/HTTP 句柄），下次操作惰性重开；serial 模式下若曾打开失败会先重载 config 再打开，返回 `{released, mode}`
- WiFi 配置（仅 serial）：
  - `set_wifi(ssid: str, password: str) -> str` — serial 发送 ASCII 命令 `wifi:<ssid>,pwd:<password>\n`；network 返回 `set_wifi not supported in network mode`

后端接口（BaseClient，serial/network 都实现）：`turn_on_ack(ch)->int` / `turn_off_ack(ch)->int` / `toggle(ch)->int` / `query(ch)->int` / `release_serial()->dict` / `set_wifi(ssid,pwd)->str` / `close()`，返回继电器吸合状态 0/1，上层 RelayService 按 active_high 换算上下电语义。

#### Scenario: 设备层上电（serial, active_high=true）
- WHEN AI 调用 `power_on(device="relay_1")` 且 mode=serial、active_high=true
- THEN RelayService 调 `SerialClient.turn_on_ack(1)`，发送 4 字节帧 `A0 01 03 A4`
  - AND 收到回包 `A0 01 01 A2` 后返回 `{"device":"relay_1","channel":1,"relay_state":1,"relay_on":true,"powered":true,"note":""}`

#### Scenario: 设备层上电（network）
- WHEN AI 调用 `power_on(device="relay_1")` 且 mode=network、active_high=true
- THEN RelayService 调 `NetworkClient.turn_on_ack(1)`，发送 `POST /api/relay` body `{"ch":1,"state":1}`
  - AND 从返回 `channels` 取第 1 路作为 relay_state，返回 `{"device":"relay_1","channel":1,"relay_state":1,"relay_on":true,"powered":true,"note":""}`

#### Scenario: 低电平触发模块（active_high=false）
- WHEN 设备 active_high=false 且调用 `power_on`
- THEN RelayService 调 `turn_off_ack`（继电器断开=设备上电），返回 `powered=true` 当 relay_state=0

#### Scenario: 继电器层原始操作
- WHEN AI 调用 `relay_control(channel=2, action="off")` 且 mode=serial
- THEN 发送 `A0 02 02 A4`，返回 `{"channel":2,"relay_state":0,"relay_on":false}`

#### Scenario: 参数校验
- WHEN 调用 `relay_control(channel=99, action="on")` 或 `action="foo"`
- THEN 在发送前抛参数异常（channel 必须 1-8，action 必须 on/off/toggle/query）

#### Scenario: 串口异常重开重载配置（serial）
- WHEN serial 模式下串口写入失败 / 读超时 / 端口消失
- THEN SerialClient 关闭旧句柄
  - AND 下次操作时 RelayService 检测到 `_need_reload`，重新读 `config.json` 获取 port/baudrate
  - AND 用新配置重建 SerialClient 并打开
  - AND 重开成功后下一次工具调用继续工作；重开失败则该次工具返回错误 `serial not open`

#### Scenario: release_serial 后惰性重开
- WHEN 调用 `release_serial()` 后再调用任意设备/继电器工具
- THEN RelayService 置空 controller 并标记 `_need_reload`，下次操作重新读 config + 重建后端

## MODIFIED Requirements

### Requirement: `index.html` `<script>` 行为
- 状态初始化：页面加载后立即 `GET /api/state`；请求失败时回退到 localStorage 现状并提示「离线模式」
- 卡片点击 → 调用 `POST /api/relay`，成功后写入 localStorage 并 `render()`；失败时回滚本地状态
- 全部 NO / NC 按钮 → 调用 `POST /api/relay/all`
- 通道数 `input` change → 维持前端缓存扩缩，但 ESP32-C3 始终为 8 路，超出 1-8 的卡片提交时按后端返回 400 忽略
- 视觉 / CSS / HTML 结构不变，仍是「继电器原理图控制面板」同款 UI

## REMOVED Requirements
无
