# Checklist

- [x] `firmware/` 目录下 7 个 Python 文件骨架创建完成（Task 1.1）
- [x] `mcp_server/` 目录下 5 个文件骨架创建完成（Task 1.2）
- [x] `requirements.txt` 包含 `pyserial`、`mcp>=2`、`requests` 三行依赖（Task 1.3）
- [x] `firmware/relay.py` 实现 GPIO1-8 驱动与单例 `relays`（Task 2）
- [x] `firmware/config.py` 实现 `load_wifi/save_wifi` 存到 `/wifi.cfg`（Task 3.1）
- [x] `firmware/wifi_manager.py` 实现 STA 优先 + AP 回退 `ESP32C3-Relay` + 持续重试（Task 3.2）
- [x] `firmware/main.py` 用 `_thread.start_new_thread` 启动 WiFi 后台线程，不阻塞主循环（Task 3.3）
- [x] `firmware/serial_proto.py` 实现 4 字节 `parse` 与 `build_state`，常量 `HEADER=0xA0`（Task 4.1-4.3）
- [x] `firmware/serial_control.py` 实现 4 字节帧状态机 + WiFi ASCII 命令解析（Task 4.4）
- [x] `firmware/main.py` 定义 `CONTROL_SERIAL = 'uart0'` 常量并据此选择控制串口（Task 5.1-5.2）
- [x] `firmware/main.py` 主循环从控制串口读取字节喂给 `serial_control.handle_byte`，回包写回（Task 5.3）
- [x] `firmware/main.py` 上电立即进入串口响应主循环，不依赖 WiFi 状态（Task 5.4）
- [x] `firmware/web_server.py` 路由 `GET /api/state` 返回 `{"channels":[...]}`（Task 6.2）
- [x] `firmware/web_server.py` 路由 `POST /api/relay` 实现并返回最新状态（Task 6.3）
- [x] `firmware/web_server.py` 路由 `POST /api/relay/all`（Task 6.4）
- [x] `firmware/web_server.py` 越界 400 + CORS 头（Task 6.5）
- [x] `firmware/web_server.py` HTTP server 在 `_thread` 中运行（Task 6.6）
- [x] `firmware/web_server.py` 路由 `GET /` 返回 `index.html`（Task 7.1）
- [x] `index.html` UI、CSS、SVG、HTML 结构未变更（Task 8.1）
- [x] `index.html` `<script>` 改为 `GET /api/state` 渲染 + 失败回退（Task 8.2）
- [x] `index.html` 卡片/全局按钮走 `POST /api/relay` 等接口（Task 8.3）
- [x] `index.html` 通道数超出 1-8 时按后端 400 忽略（Task 8.4）
- [x] `mcp_server/serial_client.py` 实现 `set_relay(channel, state, with_reply=False)` 并按 `with_reply` 选 0x02/0x03 或 0x00/0x01（Task 9.2）
- [x] `mcp_server/serial_client.py` 实现 `get_relay / toggle_relay / set_all_relays / get_all_relays / set_wifi`（Task 9.3）
- [x] `mcp_server/serial_client.py` 在 ch/state 越界时发送前抛 `ValueError`（Task 9.4）
- [x] `mcp_server/serial_client.py` 实现串口异常捕获 + `reopen()` 重载 port/baudrate 配置后再 open（Task 9.5）
- [x] `mcp_server/network_client.py` 实现 `set_relay/get_relay/set_all_relays/get_all_relays/toggle_relay/set_wifi`（Task 10.2-10.4）
- [x] `mcp_server/server.py` 用 `MCPServer`（v2，`from mcp.server import MCPServer`）暴露 6 个工具并支持 `--mode/--port/--baudrate/--host/--http-port/--transport/--bind-host/--bind-port` 参数（Task 11.1-11.4、11.6）
- [x] 工具注册验证通过：`app._tool_manager._tools` 列出 6 个工具（set_relay/get_relay/toggle_relay/set_all_relays/get_all_relays/set_wifi）；参数校验与异常路径经直接调用验证均符合预期（Task 11.5）
- [x] `README.md` 含接线、烧录、CONTROL_SERIAL 说明、MCP 两种模式启动命令（Task 12）

## 验证摘要（非 checklist 项，仅记录运行时验证结果）
- 11 个 .py 全部通过 `python3 -c "import ast; ast.parse(...)"` 语法校验
- `firmware/serial_proto.py`：`parse(A0 01 03 A4)`→`(1,3)`、`parse(A0 01 05 A6)`→`(1,5)`、坏校验和→`None`、`addr=0`→`None`；`build_state(1,1)`→`A0 01 01 A2`、`build_state(2,0)`→`A0 02 00 A2`，与 `串口通信协议` 文档示例完全一致
- `firmware/serial_control.py`：`wifi:long,pwd:longlong\n`→回 `WIFI SAVED, REBOOTING\n` + 保存 `{ssid:'long',pwd:'longlong'}`（用户原话示例）；`wifi:bad\n`→回 `ERROR: bad format, expected wifi:<ssid>,pwd:<password>\n`；1 号通道查询 `A0 01 05 A6`→回 `A0 01 00 A1`；1 号开带返回 `A0 01 03 A4`→回 `A0 01 01 A2` + ch1=1；1 号 toggle `A0 01 04 A5`→回 `A0 01 00 A1` + ch1=0
- `mcp_server/server.py`：`pip install -r requirements.txt`（锁 `mcp<2`）后 `import server` 成功，`app._tool_manager._tools` 列出 6 个工具
- serial 模式 fake port：`set_relay(99,1)`→`{'error':'channel must be 1-8'}`、`get_relay(1)`→`{'channel':1,'state':-1,'error':'serial not open'}`、`set_wifi('x','y')`→`'ERROR: serial not open'`
- network 模式 fake host：`set_relay(1,1)`→`{'ok':False,'channel':1,'state':1,'error':'...Connection refused'}`、`set_wifi('a','b')`→`'set_wifi not supported in network mode'`、`set_relay(99,1)`→`{'error':'channel must be 1-8'}`
