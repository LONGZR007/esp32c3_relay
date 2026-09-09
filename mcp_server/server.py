# -*- coding: utf-8 -*-
"""ESP32-C3 8 路继电器 MCP 服务。

把继电器控制封装成 MCP 工具，供 AI（如 Claude）调用，实现对多路设备的上电/下电控制。
后端支持 serial（pyserial 直连 ESP32-C3，4 字节帧协议）与 network（HTTP JSON API 调 ESP32）两种，
由 config.json 的 mode 字段决定。

对外暴露三层工具：

1. 设备层（面向"上下电"语义，推荐 AI 优先使用）：
   - list_devices()       列出所有设备及其通道映射、当前上下电状态
   - power_on(device)     给设备上电
   - power_off(device)    给设备下电
   - power_toggle(device) 翻转设备上下电
   - power_status(device) 查询单个设备上下电状态

2. 继电器层（原始通道控制，按通道号直接操作）：
   - relay_control(channel, action)  action ∈ {on, off, toggle, query}

3. 资源管理：
   - release_serial()   释放底层连接（串口/HTTP 句柄），后续调用会自动重开

4. WiFi 配置（仅 serial 模式）：
   - set_wifi(ssid, password)  通过 ASCII 命令配置 ESP32-C3 的 WiFi

用法::

    python server.py
    python server.py --config /path/to/config.json
    python server.py --transport streamable-http --host 0.0.0.0 --port 8000
    python server.py --transport streamable-http --no-stateless-http

配置 (config.json):
    - mode: serial | network
    - port / baudrate: serial 模式的串口设备与波特率（RELAY_PORT 环境变量覆盖 port）
    - host / http_port: network 模式 ESP32-C3 的 IP 与 HTTP 端口
    - devices[]: 每个设备 {name, channel 1-8, active_high, note}
      active_high=true 表示"上电=继电器吸合(GPIO高)"，false 表示"上电=继电器断开(低电平触发)"
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from mcp.server import MCPServer

from base_client import BaseClient
from serial_client import SerialClient
from network_client import NetworkClient

DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.json"

# MCP 服务实例
mcp = MCPServer("esp32c3-relay")

# 服务实例（惰性初始化，main() 中赋值）
_service: "RelayService | None" = None


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------
def load_config(path: str) -> Dict[str, Any]:
    """加载 JSON 配置，并做基本校验。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"配置文件不存在: {p}")

    with open(p, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    if not isinstance(cfg, dict):
        raise ValueError("配置文件顶层必须是 JSON 对象")

    mode = str(cfg.get("mode", "serial")).strip()
    if mode not in ("serial", "network"):
        raise ValueError(f"mode 非法: {mode!r}，应为 serial 或 network")

    port = None
    baudrate = int(cfg.get("baudrate", 9600))
    host = None
    http_port = int(cfg.get("http_port", 80))

    if mode == "serial":
        # 环境变量 RELAY_PORT 优先于 config.json 的 port
        port = os.environ.get("RELAY_PORT") or cfg.get("port")
        if not port:
            raise ValueError("serial 模式缺少串口：请在 config.json 设置 port，或用环境变量 RELAY_PORT 指定")
    else:
        host = cfg.get("host")
        if not host:
            raise ValueError("network 模式缺少 host：请在 config.json 设置 host")

    devices_raw = cfg.get("devices") or []
    if not devices_raw:
        raise ValueError("config.json 中 devices 列表为空，请至少配置一个设备")

    devices = []
    channels = set()
    for d in devices_raw:
        name = str(d.get("name", "")).strip()
        channel = d.get("channel")
        if not name:
            raise ValueError(f"设备缺少 name 字段: {d!r}")
        if not isinstance(channel, int) or not (1 <= channel <= 8):
            raise ValueError(f"设备 {name!r} 的通道号非法（应为 1-8 的整数）: {channel!r}")
        if channel in channels:
            raise ValueError(f"通道号重复: {channel}")
        channels.add(channel)
        devices.append({
            "name": name,
            "channel": channel,
            "active_high": bool(d.get("active_high", True)),
            "note": str(d.get("note", "")),
        })

    return {
        "mode": mode,
        "port": str(port) if port else None,
        "baudrate": baudrate,
        "host": str(host) if host else None,
        "http_port": http_port,
        "devices": devices,
    }


# ---------------------------------------------------------------------------
# 服务封装
# ---------------------------------------------------------------------------
class RelayService:
    """持有配置与后端 client，提供上下电语义接口。"""

    def __init__(self, config_path: str):
        self._config_path = str(config_path)
        self._need_reload = False
        self._controller: BaseClient | None = None
        self._load_config()

    def _load_config(self) -> None:
        """（重新）读取配置文件，更新后端参数与设备映射。"""
        config = load_config(self._config_path)
        self.mode = config["mode"]
        self.port = config["port"]
        self.baudrate = config["baudrate"]
        self.host = config["host"]
        self.http_port = config["http_port"]
        self._devices = {d["name"]: d for d in config["devices"]}

    def _build_controller(self) -> BaseClient:
        """按 mode 构造后端 client（不打开，SerialClient 在 __init__ 即 open）。"""
        if self.mode == "serial":
            return SerialClient(self.port, baudrate=self.baudrate)
        return NetworkClient(self.host, http_port=self.http_port)

    # -- 后端（惰性打开，进程内复用） --
    @property
    def controller(self) -> BaseClient:
        if self._controller is None:
            # 上次打开失败后，再次打开前重新读一次 config，以适配端口变更等。
            if self._need_reload:
                self._load_config()
                self._need_reload = False
            controller = self._build_controller()
            self._controller = controller
        return self._controller

    def close(self) -> None:
        if self._controller is not None:
            self._controller.close()
            self._controller = None

    def release_serial(self) -> Dict[str, Any]:
        """释放底层连接（串口/HTTP 句柄）。

        释放后再次调用任何设备/继电器工具时，会惰性重新打开，
        因此本方法不会影响后续操作。
        """
        if self._controller is None:
            return {"released": False, "mode": self.mode}
        result = self._controller.release_serial()
        # network 模式下 release 返回 released=False（无串口）；serial 返回 released=was_open
        # 释放后置空句柄，下次操作重建（且会先重载 config）
        if self.mode == "serial":
            self._controller = None
            self._need_reload = True
        return result

    # -- 设备解析 --
    def resolve(self, device: str) -> Dict[str, Any]:
        """按名称或通道号解析设备。"""
        if device in self._devices:
            return self._devices[device]
        if str(device).strip().isdigit():
            ch = int(device)
            for d in self._devices.values():
                if d["channel"] == ch:
                    return d
        names = ", ".join(
            f"{d['name']}(通道{d['channel']})" for d in self._devices.values()
        )
        raise ValueError(f"未知设备 {device!r}，可用设备: {names}")

    def available_names(self) -> List[str]:
        return list(self._devices.keys())

    # -- 上下电语义映射 --
    @staticmethod
    def relay_to_powered(dev: Dict[str, Any], relay_state: int) -> bool:
        """继电器吸合状态 -> 设备是否上电（结合 active_high 接线方式）。"""
        return bool(relay_state) if dev["active_high"] else not bool(relay_state)

    @staticmethod
    def powered_to_relay_on(dev: Dict[str, Any]) -> bool:
        """设备要上电时，继电器应吸合(true)还是断开(false)。"""
        return dev["active_high"]

    # -- 设备层操作（带应答，返回实测状态） --
    def power_on(self, device: str) -> Dict[str, Any]:
        dev = self.resolve(device)
        if self.powered_to_relay_on(dev):
            state = self.controller.turn_on_ack(dev["channel"])
        else:
            state = self.controller.turn_off_ack(dev["channel"])
        return self._result(dev, state)

    def power_off(self, device: str) -> Dict[str, Any]:
        dev = self.resolve(device)
        if self.powered_to_relay_on(dev):
            state = self.controller.turn_off_ack(dev["channel"])
        else:
            state = self.controller.turn_on_ack(dev["channel"])
        return self._result(dev, state)

    def power_toggle(self, device: str) -> Dict[str, Any]:
        dev = self.resolve(device)
        state = self.controller.toggle(dev["channel"])
        return self._result(dev, state)

    def power_status(self, device: str) -> Dict[str, Any]:
        dev = self.resolve(device)
        state = self.controller.query(dev["channel"])
        return self._result(dev, state)

    def _result(self, dev: Dict[str, Any], relay_state: int) -> Dict[str, Any]:
        return {
            "device": dev["name"],
            "channel": dev["channel"],
            "relay_state": relay_state,
            "relay_on": bool(relay_state),
            "powered": self.relay_to_powered(dev, relay_state),
            "note": dev["note"],
        }

    # -- 继电器层原始操作 --
    def relay_control(self, channel: int, action: str) -> Dict[str, Any]:
        action = action.lower().strip()
        if action == "on":
            state = self.controller.turn_on_ack(channel)
        elif action == "off":
            state = self.controller.turn_off_ack(channel)
        elif action == "toggle":
            state = self.controller.toggle(channel)
        elif action == "query":
            state = self.controller.query(channel)
        else:
            raise ValueError(f"非法 action {action!r}，可选: on / off / toggle / query")
        return {"channel": channel, "relay_state": state, "relay_on": bool(state)}

    # -- WiFi 配置（仅 serial） --
    def set_wifi(self, ssid: str, password: str) -> str:
        if self.mode != "serial":
            return "set_wifi not supported in network mode"
        return self.controller.set_wifi(ssid, password)


def get_service() -> RelayService:
    if _service is None:
        raise RuntimeError("服务未初始化")
    return _service


@mcp.tool()
def list_devices() -> List[Dict[str, Any]]:
    """列出所有已配置设备：名称、通道号、接线方式(active_high)及当前上下电状态。

    查询过程中若某个通道无响应，该设备会以 powered=null 并附带 error 信息返回，
    不影响其它设备。
    """
    svc = get_service()
    results = []
    for d in svc._devices.values():
        item = {
            "device": d["name"],
            "channel": d["channel"],
            "active_high": d["active_high"],
            "note": d["note"],
        }
        try:
            state = svc.controller.query(d["channel"])
            item["relay_state"] = state
            item["relay_on"] = bool(state)
            item["powered"] = svc.relay_to_powered(d, state)
            item["error"] = None
        except Exception as e:  # noqa: BLE001
            item["relay_state"] = None
            item["relay_on"] = None
            item["powered"] = None
            item["error"] = str(e)
        results.append(item)
    return results


@mcp.tool()
def power_on(device: str) -> Dict[str, Any]:
    """给指定设备上电（按名称或通道号）。返回上电后的实测状态。

    Args:
        device: 设备名称，或通道号（如 "relay_1" 或 "1"）。
    """
    return get_service().power_on(device)


@mcp.tool()
def power_off(device: str) -> Dict[str, Any]:
    """给指定设备下电（按名称或通道号）。返回下电后的实测状态。

    Args:
        device: 设备名称，或通道号。
    """
    return get_service().power_off(device)


@mcp.tool()
def power_toggle(device: str) -> Dict[str, Any]:
    """翻转指定设备的上下电状态（按名称或通道号）。返回翻转后的实测状态。

    Args:
        device: 设备名称，或通道号。
    """
    return get_service().power_toggle(device)


@mcp.tool()
def power_status(device: str) -> Dict[str, Any]:
    """查询指定设备当前上下电状态（不改变状态，按名称或通道号）。

    Args:
        device: 设备名称，或通道号。
    """
    return get_service().power_status(device)


@mcp.tool()
def relay_control(channel: int, action: str) -> Dict[str, Any]:
    """按通道号直接操作继电器（不区分设备语义）。

    Args:
        channel: 继电器通道号（1-8 的整数）。
        action: 操作类型，可选 "on"（吸合）、"off"（断开）、
                "toggle"（翻转）、"query"（仅查询）。
    """
    return get_service().relay_control(channel, action)


@mcp.tool()
def release_serial() -> Dict[str, Any]:
    """释放底层连接（关闭当前串口/HTTP 句柄），释放占用的资源。

    释放后再次调用任何设备/继电器工具时会自动重新打开，
    不会影响后续操作。串口模式下若曾打开失败会先重载 config 再打开。
    """
    return get_service().release_serial()


@mcp.tool()
def set_wifi(ssid: str, password: str) -> str:
    """配置 ESP32-C3 的 WiFi 连接（仅 serial 模式可用）。

    通过串口发送 ASCII 命令 wifi:<ssid>,pwd:<password>，设备保存后重启。
    network 模式下 HTTP 接口不暴露 WiFi 设置，调用返回错误信息。

    Args:
        ssid: WiFi 名称。
        password: WiFi 密码。
    """
    return get_service().set_wifi(ssid, password)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="ESP32-C3 8 路继电器 MCP 服务")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help="配置文件路径（默认 config.json）")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"],
                        default="stdio", help="MCP 传输方式（默认 stdio）")
    parser.add_argument("--host", default="127.0.0.1", help="sse/http 监听地址")
    parser.add_argument("--port", type=int, default=8000, help="sse/http 监听端口")
    parser.add_argument(
        "--stateless-http",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="streamable-http 使用无状态模式（默认开）。"
             "无状态模式不要求客户端回传 session id，兼容 Claude Code 等 HTTP 客户端；"
             "用 --no-stateless-http 关闭（需要客户端维护 mcp-session-id）。",
    )
    args = parser.parse_args()

    global _service
    _service = RelayService(args.config)

    # host/port/stateless_http 等按传输方式作为 run() 的关键字参数传入。
    try:
        if args.transport == "stdio":
            mcp.run(transport="stdio")
        elif args.transport == "sse":
            mcp.run(transport="sse", host=args.host, port=args.port)
        else:  # streamable-http
            mcp.run(
                transport="streamable-http",
                host=args.host,
                port=args.port,
                stateless_http=args.stateless_http,
            )
    finally:
        if _service is not None:
            _service.close()


if __name__ == "__main__":
    main()
