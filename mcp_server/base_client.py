class BaseClient:
    """MCP 服务器后端接口。serial_client.SerialClient 与 network_client.NetworkClient 都实现这套方法。"""
    def set_relay(self, channel, state, with_reply=False): raise NotImplementedError
    def get_relay(self, channel): raise NotImplementedError
    def toggle_relay(self, channel): raise NotImplementedError
    def set_all_relays(self, state): raise NotImplementedError
    def get_all_relays(self): raise NotImplementedError
    def set_wifi(self, ssid, password): raise NotImplementedError
