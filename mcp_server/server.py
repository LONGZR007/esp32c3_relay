# ESP32-C3 8 路继电器 MCP 服务器
import argparse
from mcp.server import MCPServer
from serial_client import SerialClient
from network_client import NetworkClient

app = MCPServer("esp32c3-relay")

# 全局后端实例
_backend = None


def _get_backend():
    global _backend
    if _backend is None:
        raise RuntimeError("backend not initialized")
    return _backend


@app.tool()
def set_relay(channel: int, state: int, with_reply: bool = False) -> dict:
    """设置单路继电器状态。channel 1-8，state 0(关)/1(开)。with_reply=True 时串口模式下使用应答协议确认。返回 {"ok":..., "channel":N, "state":S}。"""
    try:
        return _get_backend().set_relay(channel, state, with_reply)
    except Exception as e:
        return {"error": str(e)}


@app.tool()
def get_relay(channel: int) -> dict:
    """查询单路继电器当前状态。channel 1-8。返回 {"channel":N, "state":S}，state 为 0(关)/1(开) 或 -1(查询失败)。"""
    try:
        return _get_backend().get_relay(channel)
    except Exception as e:
        return {"error": str(e)}


@app.tool()
def toggle_relay(channel: int) -> dict:
    """翻转单路继电器状态。channel 1-8。返回 {"channel":N, "state":S}，state 为翻转后的新状态。"""
    try:
        return _get_backend().toggle_relay(channel)
    except Exception as e:
        return {"error": str(e)}


@app.tool()
def set_all_relays(state: int) -> dict:
    """批量设置所有 8 路继电器状态。state 0(全关)/1(全开)。返回 {"ok":..., "state":S}。"""
    try:
        return _get_backend().set_all_relays(state)
    except Exception as e:
        return {"error": str(e)}


@app.tool()
def get_all_relays() -> list:
    """查询全部 8 路继电器状态。返回 [{"channel":1,"state":S}, ..., {"channel":8,"state":S}]。"""
    try:
        return _get_backend().get_all_relays()
    except Exception as e:
        return [{"error": str(e)}]


@app.tool()
def set_wifi(ssid: str, password: str) -> str:
    """配置 ESP32-C3 的 WiFi 连接（仅串口模式可用）。ssid 为 WiFi 名称，password 为密码。返回操作结果字符串。"""
    try:
        return _get_backend().set_wifi(ssid, password)
    except Exception as e:
        return "ERROR: " + str(e)


def main():
    parser = argparse.ArgumentParser()
    # 控制通道：MCP 服务器通过哪种方式把命令发给 ESP32-C3
    parser.add_argument("--mode", required=True, choices=["serial", "network"])
    # serial 模式：ESP32-C3 的串口
    parser.add_argument("--port")
    parser.add_argument("--baudrate", type=int, default=115200)
    # network 模式：ESP32-C3 的 IP 与 HTTP 端口
    parser.add_argument("--host")
    parser.add_argument("--http-port", type=int, default=80)
    # MCP 服务器自身的传输：AI 客户端通过哪种方式连到本服务器
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    # streamable-http 传输：本服务器监听的地址与端口
    parser.add_argument("--bind-host", default="127.0.0.1")
    parser.add_argument("--bind-port", type=int, default=8000)
    args = parser.parse_args()

    global _backend
    if args.mode == "serial":
        if not args.port:
            raise SystemExit("--port required in serial mode")
        _backend = SerialClient(args.port, args.baudrate)
    else:
        if not args.host:
            raise SystemExit("--host required in network mode")
        _backend = NetworkClient(args.host, args.http_port)

    if args.transport == "streamable-http":
        app.run(transport="streamable-http",
                host=args.bind_host,
                port=args.bind_port)
    else:
        app.run()


if __name__ == "__main__":
    main()
