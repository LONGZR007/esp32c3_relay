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
| UART0 TX/RX | 默认 GPIO21 / GPIO20（ESP32-C3） | 默认作为**继电器/WiFi 控制串口**，115200 |
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

在控制串口（默认 UART0，115200）输入 ASCII 文本（以换行结尾）：

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

### 启动（两种模式 × 两种传输）

`--mode` 选控制通道（MCP 服务器怎么把命令发给 ESP32-C3），`--transport` 选 MCP 服务器自身的传输（AI 客户端怎么连到本服务器），二者正交组合。

**串口模式 + stdio**（默认，`mcp dev` 调试用）：

```
mcp dev mcp_server/server.py -- --mode serial --port /dev/ttyACM0 --baudrate 115200
```

**网络模式 + stdio**：

```
mcp dev mcp_server/server.py -- --mode network --host 192.168.1.50 --http-port 80
```

**串口模式 + streamable-http**（直接 `python` 跑，AI 通过 HTTP 连接）：

```
python mcp_server/server.py --mode serial --port /dev/ttyACM0 --baudrate 115200 \
    --transport streamable-http --bind-host 127.0.0.1 --bind-port 8000
```

端点：`http://127.0.0.1:8000/mcp`

> 默认 `--bind-host 127.0.0.1` 只允许本机访问。如需局域网/外网访问，改 `--bind-host 0.0.0.0` 并自行配置 `transport_security` 白名单（v2 默认对非 localhost 请求返回 421 防止 DNS 重绑定）。

> `mcp dev` 仅用于本地调试。生产可用 `mcp install` 注册到 Claude Desktop / Cursor 等 MCP 客户端。

### 工具清单

| 工具 | 参数 | 返回 | 备注 |
|---|---|---|---|
| `set_relay` | `channel 1-8`, `state 0/1`, `with_reply=false` | `{"ok":true,"channel":N,"state":S}` | serial 模式 `with_reply=true` 走 0x02/0x03 应答；network 模式忽略该参数 |
| `get_relay` | `channel 1-8` | `{"channel":N,"state":S}` | serial 用 0x05；network 走 `GET /api/state` |
| `toggle_relay` | `channel 1-8` | `{"channel":N,"state":S}` | serial 用 0x04；network 客户端先查再设 |
| `set_all_relays` | `state 0/1` | `{"ok":true,"state":S}` | serial 8 次 set；network 走 `/api/relay/all` |
| `get_all_relays` | - | `[{"channel":1,"state":S}, ...]` | serial 8 次 get；network 一次 `GET /api/state` |
| `set_wifi` | `ssid`, `password` | 回显字符串 | serial 模式发 ASCII 命令；network 模式不支持 |

### 串口异常重开

serial 模式下若串口写入失败 / 读超时 / 端口消失，MCP 服务器会自动 `close()` 旧句柄并从启动参数（`--port` / `--baudrate`）**重新加载配置**后再 `open()`，避免使用陈旧句柄；重开仍失败则该次工具返回 `serial not open`。
