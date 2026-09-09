# Tasks

- [ ] Task 1: 准备项目骨架与依赖声明
  - [ ] SubTask 1.1: 在 `firmware/` 下创建空 `main.py`、`relay.py`、`wifi_manager.py`、`web_server.py`、`serial_proto.py`、`serial_control.py`、`config.py`，作为后续实现的占位
  - [ ] SubTask 1.2: 在 `mcp_server/` 下创建空 `server.py`、`serial_client.py`、`requirements.txt`
  - [ ] SubTask 1.3: 在 `requirements.txt` 写入 `pyserial`、`mcp` 两行依赖

- [ ] Task 2: 实现继电器 HAL（GPIO1-8 驱动）
  - [ ] SubTask 2.1: 在 `firmware/relay.py` 定义 `Relays` 类，初始化 `Pin(1..8, Pin.OUT, value=0)`
  - [ ] SubTask 2.2: 提供 `set(ch, state)`、`get(ch)`、`set_all(state)`、`get_all()` 方法，`ch` 范围 1-8，越界抛 `ValueError`
  - [ ] SubTask 2.3: 提供模块级 `relays = Relays()` 单例，方便其它模块导入

- [ ] Task 3: 实现持久化 WiFi 配置管理
  - [ ] SubTask 3.1: 在 `firmware/config.py` 实现 `load_wifi()` / `save_wifi(ssid, pwd)`，存到 `/wifi.cfg`
  - [ ] SubTask 3.2: 在 `firmware/wifi_manager.py` 实现 `connect()`（先 STA，失败回退 AP 模式，AP 名为 `ESP32C3-Relay`）
  - [ ] SubTask 3.3: 在 `main.py` 中于启动阶段调用 `wifi_manager.connect()`，并打印 STA / AP 状态

- [ ] Task 4: 实现 4 字节串口协议编解码
  - [ ] SubTask 4.1: 在 `firmware/serial_proto.py` 定义常量 `HEADER = 0xA0`，功能码表与 `串口通信协议` 文档一致
  - [ ] SubTask 4.2: 实现 `parse(frame: bytes) -> (addr, func) | None`，校验 `Header` 与 `Checksum`，校验失败返回 `None`
  - [ ] SubTask 4.3: 实现 `build_state(addr, state) -> bytes` 构造 4 字节状态回包，Checksum `(H + A + S) & 0xFF`
  - [ ] SubTask 4.4: 在 `serial_control.py` 实现 `handle_byte(b: int) -> Optional[bytes]` 状态机：
    - 累积字节，凑够 4 字节尝试 `parse` → 执行 0x00/0x01/0x02/0x03/0x04/0x05 → 返回 0 / 4 字节回包
    - 同时检测 ASCII 命令行（缓冲到换行）：匹配 `wifi:<ssid>,pwd:<password>` 时调用 `config.save_wifi()` + `machine.reset()`，不匹配回显 `ERROR: bad format...`

- [ ] Task 5: 实现双串口与角色切换
  - [ ] SubTask 5.1: 在 `main.py` 启动时读取 `Pin(9, Pin.IN, Pin.PULL_UP)`
  - [ ] SubTask 5.2: 高电平 → USB CDC = REPL（默认行为），UART0 (115200) = 控制串口
  - [ ] SubTask 5.3: 低电平 → UART0 = REPL（`os.dupterm(machine.UART(0, 115200))`），USB CDC = 控制串口
  - [ ] SubTask 5.4: 控制串口在独立线程 / 主循环里轮询读取字节喂给 `serial_control.handle_byte`，回包写回控制串口

- [ ] Task 6: 实现 HTTP JSON API
  - [ ] SubTask 6.1: 在 `firmware/web_server.py` 基于原生 `socket` 实现最小 HTTP server，监听 80
  - [ ] SubTask 6.2: 路由 `GET /api/state` → 返回 `{"channels": relays.get_all()}`
  - [ ] SubTask 6.3: 路由 `POST /api/relay`（body `{"ch":1,"state":1}`）→ `relays.set` 后回 `{"channels": relays.get_all()}`
  - [ ] SubTask 6.4: 路由 `POST /api/relay/all`（body `{"state":1}`）→ `relays.set_all` 后回 `{"channels": relays.get_all()}`
  - [ ] SubTask 6.5: 越界 / 错误 JSON → HTTP 400 `{"error":"channel out of range"}`；统一加 `Access-Control-Allow-Origin: *`

- [ ] Task 7: 静态服务 `index.html`
  - [ ] SubTask 7.1: `firmware/web_server.py` 路由 `GET /` 时把 `index.html` 写入文件系统并返回（烧录时由 IDE 烧入，运行期只读）
  - SubTask 7.2: 允许 `POST /api/reload` 重读一次（可选，便于现场更新）

- [ ] Task 8: 重写 `index.html` 的 `<script>`
  - [ ] SubTask 8.1: 保持 UI（CSS、SVG、HTML 结构、卡片视觉）原样不动
  - [ ] SubTask 8.2: 启动时 `fetch('/api/state')`，成功用真实状态渲染，失败回退 localStorage
  - SubTask 8.3: 卡片点击 / 全部按钮 → `fetch('/api/relay' | '/api/relay/all', {method:'POST', body})`，成功后写 localStorage 并 `render()`，失败回滚 + console.error
  - SubTask 8.4: 通道数 change 仅扩缩本地缓存，超出 1-8 的卡片提交时若后端 400 则忽略 + 提示

- [ ] Task 9: 实现 Python 串口协议客户端
  - ] SubTask 9.1: 在 `mcp_server/serial_client.py` 实现 `open(port, baudrate=115200)`、`close()`，使用 pyserial
  - [ ] SubTask 9.2: 实现 `set_relay(ch, state, with_reply=False)`：构造 4 字节帧，发送，`with_reply=True` 时按 0x02/0x03 等待并校验回包，返回 `dict`
  - [ ] SubTask 9.3: 实现 `get_relay(ch)`（0x05）、`toggle_relay(ch)`（0x04）、`set_all_relays(state)`、`get_all_relays()`、`set_wifi(ssid, pwd)`
  - [ ] SubTask 9.4: 对 `ch` 越界（1-8）、`state` 非 0/1 在发送前抛 `ValueError`，避免误通讯

- [ ] Task 10: 实现 MCP 服务器
  - [ ] SubTask 10.1: 在 `mcp_server/server.py` 用 `from mcp.server.fastmcp import FastMCP` 创建 `app = FastMCP("esp32c3-relay")`
  - [ ] SubTask 10.2: 用 `@app.tool()` 暴露 Task 9 的全部方法，参数文档串写明含义
  - [ ] SubTask 10.3: 启动时从 `--port` 与 `--baudrate` 读取串口路径，传给 `serial_client.open(...)`
  - [ ] SubTask 10.4: `app.run()`，验证 `mcp dev mcp_server/server.py` 能列出工具且 `tools/call set_relay channel=1 state=1` 走通

- [ ] Task 11: 更新 `README.md`
  - [ ] SubTask 11.1: 写入硬件接线（GPIO1-8=继电器，GPIO9=角色开关，UART0=默认 TX/RX，USB CDC）
  - SubTask 11.2: 写入烧录 MicroPython 与上传 `firmware/`、`index.html` 的最小步骤
  - SubTask 11.3: 写入 MCP 服务器运行命令与工具示例

# Task Dependencies
- [Task 5] depends on [Task 4]
- [Task 4] depends on [Task 2]
- [Task 6] depends on [Task 2]
- [Task 7] depends on [Task 8]
- [Task 9] depends on [Task 1.3] (依赖 `requirements.txt`)
- [Task 10] depends on [Task 9]
