# Tasks

- [x] Task 1: 准备项目骨架与依赖声明
  - [x] SubTask 1.1: 在 `firmware/` 下创建 `main.py`、`relay.py`、`wifi_manager.py`、`web_server.py`、`serial_proto.py`、`serial_control.py`、`config.py`
  - [x] SubTask 1.2: 在 `mcp_server/` 下创建 `server.py`、`serial_client.py`、`network_client.py`、`base_client.py`、`requirements.txt`
  - [x] SubTask 1.3: 在 `requirements.txt` 写入 `pyserial`、`mcp>=2`、`requests` 三行依赖

- [x] Task 2: 实现继电器 HAL（GPIO1-8 驱动）
  - [x] SubTask 2.1: 在 `firmware/relay.py` 定义 `Relays` 类，初始化 `Pin(1..8, Pin.OUT, value=0)`
  - [x] SubTask 2.2: 提供 `set(ch, state)`、`get(ch)`、`set_all(state)`、`get_all()` 方法，`ch` 范围 1-8，越界抛 `ValueError`
  - [x] SubTask 2.3: 提供模块级 `relays = Relays()` 单例，方便其它模块导入

- [x] Task 3: 实现持久化 WiFi 配置管理（后台持续重试）
  - [x] SubTask 3.1: 在 `firmware/config.py` 实现 `load_wifi()` / `save_wifi(ssid, pwd)`，存到 `/wifi.cfg`
  - [x] SubTask 3.2: 在 `firmware/wifi_manager.py` 实现 `connect_loop()`：STA 优先 + AP 回退 + 持续重试，间隔不短于 5 秒，不抛未捕获异常
  - [x] SubTask 3.3: 在 `main.py` 中以 `_thread.start_new_thread(wifi_manager.connect_loop, ())` 启动后台线程

- [x] Task 4: 实现 4 字节串口协议编解码
  - [x] SubTask 4.1: 在 `firmware/serial_proto.py` 定义常量 `HEADER = 0xA0`，功能码表与 `串口通信协议` 文档一致
  - [x] SubTask 4.2: 实现 `parse(frame: bytes) -> (addr, func) | None`，校验 `Header` 与 `Checksum`，校验失败返回 `None`
  - [x] SubTask 4.3: 实现 `build_state(addr, state) -> bytes` 构造 4 字节状态回包，Checksum `(H + A + S) & 0xFF`
  - [x] SubTask 4.4: 在 `serial_control.py` 实现 `handle_byte(b: int) -> Optional[bytes]` 状态机：4 字节帧分派 + WiFi ASCII 命令解析

- [x] Task 5: 双串口角色由代码常量控制
  - [x] SubTask 5.1: 在 `firmware/main.py` 定义 `CONTROL_SERIAL = 'uart0'`（另一个取值 `'usb_cdc'`）
  - [x] SubTask 5.2: 根据 `CONTROL_SERIAL` 选择控制串口（uart0 = machine.UART(0,115200)；usb_cdc = sys.stdin/stdout + REPL 转 UART0）
  - [x] SubTask 5.3: 主循环从控制串口读取字节喂给 `serial_control.handle_byte`，回包写回；不依赖外部引脚
  - [x] SubTask 5.4: 上电立即进入主循环响应串口，不依赖 WiFi 状态

- [x] Task 6: 实现 HTTP JSON API
  - [x] SubTask 6.1: 在 `firmware/web_server.py` 基于原生 `socket` 实现最小 HTTP server，监听 80
  - [x] SubTask 6.2: 路由 `GET /api/state` → 返回 `{"channels": relays.get_all()}`
  - [x] SubTask 6.3: 路由 `POST /api/relay`（body `{"ch":1,"state":1}`）→ `relays.set` 后回 `{"channels": relays.get_all()}`
  - [x] SubTask 6.4: 路由 `POST /api/relay/all`（body `{"state":1}`）→ `relays.set_all` 后回 `{"channels": relays.get_all()}`
  - [x] SubTask 6.5: 越界 / 错误 JSON → HTTP 400 `{"error":"channel out of range"}`；统一加 `Access-Control-Allow-Origin: *`
  - [x] SubTask 6.6: HTTP server 在 `_thread` 中运行，与串口主循环并行

- [x] Task 7: 静态服务 `index.html`
  - [x] SubTask 7.1: `firmware/web_server.py` 路由 `GET /` 时读取并返回 `index.html`（烧录时由 IDE 烧入，运行期只读）
  - SubTask 7.2: 允许 `POST /api/reload` 重读一次（可选，未实现，spec 标记可选）

- [x] Task 8: 重写 `index.html` 的 `<script>`
  - [x] SubTask 8.1: 保持 UI（CSS、SVG、HTML 结构、卡片视觉）原样不动
  - [x] SubTask 8.2: 启动时 `fetch('/api/state')`，成功用真实状态渲染，失败回退 localStorage
  - [x] SubTask 8.3: 卡片点击 / 全部按钮 → `fetch('/api/relay' | '/api/relay/all', {method:'POST', body})`，成功后写 localStorage 并 `render()`，失败回滚 + console.error
  - [x] SubTask 8.4: 通道数 change 仅扩缩本地缓存，超出 1-8 的卡片提交时若后端 400 则忽略 + 提示

- [x] Task 9: 实现 Python 串口协议客户端（serial 模式后端）
  - [x] SubTask 9.1: 在 `mcp_server/serial_client.py` 实现 `open(port, baudrate)`、`close()`，使用 pyserial
  - [x] SubTask 9.2: 实现 `set_relay(ch, state, with_reply=False)`：构造 4 字节帧，发送，`with_reply=True` 时按 0x02/0x03 等待并校验回包，返回 `dict`
  - [x] SubTask 9.3: 实现 `get_relay(ch)`（0x05）、`toggle_relay(ch)`（0x04）、`set_all_relays(state)`、`get_all_relays()`、`set_wifi(ssid, pwd)`
  - [x] SubTask 9.4: 对 `ch` 越界（1-8）、`state` 非 0/1 在发送前抛 `ValueError`
  - [x] SubTask 9.5: 实现串口异常捕获 + `reopen()` 重载 port/baudrate 配置后再 open（_ensure_open 在句柄无效时自动 reopen）

- [x] Task 10: 实现 HTTP 网络客户端（network 模式后端）
  - [x] SubTask 10.1: 在 `mcp_server/network_client.py` 实现 `__init__(host, http_port)`，使用 `requests`
  - [x] SubTask 10.2: 实现 `set_relay/get_relay/set_all_relays/get_all_relays` 走对应 HTTP 路由
  - [x] SubTask 10.3: `toggle_relay` 在客户端先 `get_relay` 再 `set_relay(取反)`
  - [x] SubTask 10.4: `set_wifi` 直接返回错误字符串 `set_wifi not supported in network mode`

- [x] Task 11: 实现 MCP 服务器
  - [x] SubTask 11.1: 在 `mcp_server/server.py` 用 `from mcp.server import MCPServer` 创建 `app = MCPServer("esp32c3-relay")`（v2 API；`@app.tool()` 与 `app.run()` 写法不变）
  - [x] SubTask 11.2: 解析 `--mode`/`--port`/`--baudrate`/`--host`/`--http-port` 命令行参数
  - [x] SubTask 11.3: 根据 `--mode` 实例化 `SerialClient` 或 `NetworkClient` 作为后端
  - [x] SubTask 11.4: 用 `@app.tool()` 暴露 6 个工具，每个工具调用后端方法并返回结果；参数文档串写明含义
  - [x] SubTask 11.5: 工具注册验证通过（`app._tool_manager._tools` 列出 6 个工具：set_relay/get_relay/toggle_relay/set_all_relays/get_all_relays/set_wifi）；直接调用 set_relay(99,1) 返回 `{'error':'channel must be 1-8'}`，get_relay(1) 在 serial not open 时返回 `{'channel':1,'state':-1,'error':'serial not open'}`，network set_wifi 返回 `set_wifi not supported in network mode`

- [x] Task 12: 更新 `README.md`
  - [x] SubTask 12.1: 写入硬件接线（GPIO1-8=继电器，UART0=默认 TX/RX，USB CDC）
  - [x] SubTask 12.2: 写入烧录 MicroPython 与上传 `firmware/`、`index.html` 的最小步骤
  - [x] SubTask 12.3: 写入 `main.py` 中 `CONTROL_SERIAL` 常量的两种取值含义
  - [x] SubTask 12.4: 写入 MCP 服务器两种模式启动命令与工具示例

# Task Dependencies
- [Task 5] depends on [Task 4]
- [Task 4] depends on [Task 2]
- [Task 6] depends on [Task 2]
- [Task 7] depends on [Task 8]
- [Task 9] depends on [Task 1.3]
- [Task 10] depends on [Task 1.3]
- [Task 11] depends on [Task 9] 与 [Task 10]
