# 后端接口基类：serial 与 network 两个 client 都实现这套方法
# 方法返回继电器吸合状态（0=断开 / 1=吸合），上层 RelayService 再按 active_high 换算成上下电语义


class BaseClient:
    """MCP 服务器后端接口。SerialClient 与 NetworkClient 都实现这套方法。"""

    def turn_on_ack(self, channel: int) -> int:
        """继电器吸合（带应答），返回实测吸合状态 0/1。"""
        raise NotImplementedError

    def turn_off_ack(self, channel: int) -> int:
        """继电器断开（带应答），返回实测吸合状态 0/1。"""
        raise NotImplementedError

    def toggle(self, channel: int) -> int:
        """翻转继电器，返回翻转后实测吸合状态 0/1。"""
        raise NotImplementedError

    def query(self, channel: int) -> int:
        """查询继电器当前吸合状态，返回 0/1。"""
        raise NotImplementedError

    def release_serial(self) -> dict:
        """释放底层连接（串口/HTTP 句柄），下次操作会惰性重开。

        network 模式无串口，返回 {"released": False, "mode": "network"}。
        """
        return {"released": False, "mode": "network"}

    def set_wifi(self, ssid: str, password: str) -> str:
        """配置 ESP32-C3 的 WiFi。network 模式不支持，返回错误字符串。"""
        return "set_wifi not supported in network mode"

    def close(self) -> None:
        """关闭并释放底层资源。"""
        pass
