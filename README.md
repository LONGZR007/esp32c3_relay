# esp32c3_relay

基于 ESP32-C3（MicroPython）的 8 路继电器控制方案，支持 **网页控制**、**串口协议控制** 与 **AI 通过 MCP 控制** 三种通道，UI 不破坏原 `index.html` 视觉。

## 目录结构

```
.
├── index.html              # 网页控制面板（UI 不变，<script> 已改为调用 HTTP API）
├── 串口通信协议             # 4 字节串口协议说明
├── firmware/               # ESP32-C3 MicroPython 固件
│   ├── main.py             # 启动主程序，CONTROL_SERIAL 常量在此
│   ├── relay.py            # GPIO1-8 继电器 HAL
│   ├── config.py           # /wifi.cfg 读写
│   ├── wifi_manager.py     # STA 优先 + AP 回退，后台持续重试
│   ├── serial_proto.py     # 4 字节协议编解码
│   ├── serial_control.py   # 帧状态机 + wifi ASCII 命令
│   ├── web_server.py       # HTTP JSON API + 静态服务 index.html
│   └── index.html          # 与根目录一致的网页（烧入设备）
└── mcp_server/             # Python MCP 服务器
    ├── server.py            # MCPServer (mcp v2) 暴露 6 个工具
    ├── serial_client.py    # 串口模式后端（pyserial + 4 字节协议）
    ├── network_client.py   # 网络模式后端（requests + HTTP API）
    ├── base_client.py      # 后端接口基类
    └── requirements.txt    # pyserial / mcp>=2 / requests
```

## 硬件接线

| 信号 | 引脚 | 说明 |
|---|---|---|
| 继电器 CH1 ~ CH8 | GPIO1 ~ GPIO8 | 高电平 = 吸合（状态 1），低电平 = 不吸合（状态 0） |
| UART0 TX/RX | 默认 GPIO21 / GPIO20（ESP32-C3） | 默认作为**继电器/WiFi 控制串口**，9600 |
| USB CDC | 板载 USB 口 | 默认作为 **REPL** |

## 串口角色配置

在 [firmware/main.py](firmware/main.py) 顶部修改 `CONTROL_SERIAL` 常量：

```python
CONTROL_SERIAL = 'uart0'      # 默认：UART0 = 控制串口，USB CDC = REPL
# CONTROL_SERIAL = 'usb_cdc'  # 切换：USB CDC = 控制串口，UART0 = REPL
```

修改后重新上传 `main.py` 重启即可，**不依赖任何物理开关**。两种模式下控制串口都跑同一套 4 字节协议 + `wifi:` ASCII 命令。

## 烧录与上传

1. 用 [MicroPython ESP32-C3 固件](https://micropython.org/download/ESP32_GENERIC_C3/) 烧录到设备（esptool 或 mpremote 均可）。
2. 把 `firmware/` 下 7 个 `.py` 文件 + `firmware/index.html` 全部上传到设备根目录（mpremote / Thonny / VSCode MicroPython 插件均可）：
   ```
   mpremote cp firmware/main.py firmware/relay.py firmware/config.py firmware/wifi_manager.py firmware/serial_proto.py firmware/serial_control.py firmware/web_server.py firmware/index.html :
   ```
3. 上电后：
   - **立即** 通过控制串口可控制继电器（不等 WiFi）
   - 后台线程持续尝试连接 `/wifi.cfg` 中的 WiFi，连不上时回退到 AP 模式（AP 名 `ESP32C3-Relay`，无密码）
   - WiFi 联网后浏览器访问 `http://<设备IP>/` 即可看到控制面板

## 通过串口配置 WiFi

在控制串口（默认 UART0，9600）输入 ASCII 文本（以换行结尾）：

```
wifi:<ssid>,pwd:<password>
```

例如：

```
wifi:MyHome,pwd:longlong
```

设备回显 `WIFI SAVED, REBOOTING` 后自动重启，重启后尝试连接新 WiFi。格式错误时回显 `ERROR: bad format, expected wifi:<ssid>,pwd:<password>` 且不重启。

## 串口继电器协议

完全遵循 [串口通信协议](串口通信协议)：定长 4 字节帧，Header=`0xA0`，Checksum=`(H+A+F)&0xFF`，功能码 0x00~0x05，带应答指令回送 4 字节状态帧。地址码 0x01~0x08 对应 1~8 号通道。

## HTTP API（网页与 MCP 网络模式共用）

| 方法 | 路径 | Body | 返回 |
|---|---|---|---|
| GET | `/api/state` | - | `{"channels":[0,0,0,0,0,0,0,0]}` |
| POST | `/api/relay` | `{"ch":1,"state":1}` | `{"channels":[1,0,0,0,0,0,0,0]}` |
| POST | `/api/relay/all` | `{"state":1}` | `{"channels":[1,1,1,1,1,1,1,1]}` |
| GET | `/` | - | `index.html` |

所有响应带 `Access-Control-Allow-Origin: *`。`ch` 越界（不在 1-8）返回 HTTP 400 `{"error":"channel out of range"}`。

## MCP 服务器

### 安装依赖

```
pip install -r mcp_server/requirements.txt
```

### 配置 (config.json)

后端（serial/network）与设备映射都写在 `mcp_server/config.json`：

```json
{
  "mode": "serial",
  "port": "COM6",
  "baudrate": 9600,
  "host": "192.168.1.50",
  "http_port": 80,
  "devices": [
    { "name": "relay_1", "channel": 1, "active_high": true, "note": "路由器" },
    ...
  ]
}
```

- `mode`：`serial` 用 `port`/`baudrate` 直连 ESP32-C3；`network` 用 `host`/`http_port` 调 HTTP API
- `port` 可被环境变量 `RELAY_PORT` 覆盖（不改文件临时换串口）
- `devices[]`：给 8 路起设备名，`active_high=true` 表示"上电=继电器吸合(GPIO高)"，`false` 表示"上电=继电器断开(低电平触发模块)"，`note` 写设备用途备注

### 启动（控制通道由 config.json 决定，传输由命令行决定）

`--transport` 选 MCP 服务器自身的传输（AI 客户端怎么连到本服务器），与后端 mode 正交。

**stdio**（默认，`mcp dev` 调试用）：

```
mcp dev mcp_server/server.py
```

**streamable-http**（直接 `python` 跑，AI 通过 HTTP 连接）：

```
python mcp_server/server.py --transport streamable-http --host 0.0.0.0 --port 8000
```

端点：`http://<host>:<port>/mcp`。`--no-stateless-http` 切到有状态模式（需客户端维护 session id，默认无状态兼容 Claude Code 等）。

> `--host 0.0.0.0` 绑定所有网卡，但 v2 默认对非 localhost 请求返回 421 防 DNS 重绑定；如需局域网访问要配 `transport_security` 白名单，或先用 `127.0.0.1` 本机验证。

> 临时换串口不改文件：`RELAY_PORT=/dev/ttyUSB1 python mcp_server/server.py`

### 工具清单（三层语义）

**设备层**（面向上下电语义，推荐 AI 优先用）：

| 工具 | 参数 | 返回 |
|---|---|---|
| `list_devices` | - | `[{device, channel, active_high, note, relay_state, relay_on, powered, error}]`（某路无响应该路 powered=null 并附 error） |
| `power_on` | `device`（名称或通道号，如 `relay_1` 或 `"1"`） | `{device, channel, relay_state, relay_on, powered, note}` |
| `power_off` | `device` | 同上 |
| `power_toggle` | `device` | 翻转后状态 |
| `power_status` | `device` | 当前状态 |

**继电器层**（原始通道控制）：

| 工具 | 参数 | 返回 |
|---|---|---|
| `relay_control` | `channel 1-8`, `action ∈ {on, off, toggle, query}` | `{channel, relay_state, relay_on}` |

**资源管理 / WiFi**：

| 工具 | 参数 | 返回 |
|---|---|---|
| `release_serial` | - | `{released, mode}`（关闭底层连接，下次操作惰性重开） |
| `set_wifi` | `ssid`, `password` | 回显字符串（仅 serial；network 返回 `set_wifi not supported in network mode`） |

### 串口异常重开

serial 模式下若串口写入失败 / 读超时 / 端口消失，SerialClient 会 `close()` 旧句柄；下次操作时 RelayService 检测到 `_need_reload`，**重新读 `config.json`** 获取 port/baudrate 后重建 SerialClient 并 open，避免使用陈旧句柄；重开仍失败则该次工具返回 `serial not open`。
