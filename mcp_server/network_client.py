# 网络后端：通过 HTTP JSON API 调用 ESP32-C3
import requests
from base_client import BaseClient


class NetworkClient(BaseClient):
    def __init__(self, host: str, http_port: int = 80):
        self.base = "http://{}:{}".format(host, http_port)

    def _get(self, path):
        # GET 请求，返回 JSON
        r = requests.get(self.base + path, timeout=5)
        r.raise_for_status()
        return r.json()

    def _post(self, path, body):
        # POST 请求，返回 JSON
        r = requests.post(self.base + path, json=body, timeout=5)
        r.raise_for_status()
        return r.json()

    def set_relay(self, channel: int, state: int, with_reply: bool = False) -> dict:
        # 设置单路继电器。channel 1-8，state 0/1。
        if channel < 1 or channel > 8:
            raise ValueError("channel must be 1-8")
        if state not in (0, 1):
            raise ValueError("state must be 0 or 1")
        try:
            resp = self._post("/api/relay", {"ch": channel, "state": state})
            channels = resp.get("channels", [])
            if len(channels) >= channel:
                new_state = channels[channel - 1]
            else:
                new_state = state
            return {"ok": True, "channel": channel, "state": new_state}
        except Exception as e:
            return {"ok": False, "channel": channel, "state": state, "error": str(e)}

    def get_relay(self, channel: int) -> dict:
        # 查询单路继电器状态。channel 1-8。
        if channel < 1 or channel > 8:
            raise ValueError("channel must be 1-8")
        channels = self._get("/api/state").get("channels", [])
        if len(channels) >= channel:
            state = channels[channel - 1]
        else:
            state = -1
        return {"channel": channel, "state": state}

    def toggle_relay(self, channel: int) -> dict:
        # 翻转单路继电器。channel 1-8。
        if channel < 1 or channel > 8:
            raise ValueError("channel must be 1-8")
        try:
            cur = self.get_relay(channel)["state"]
            new_state = 1 - cur
            self.set_relay(channel, new_state)
            return {"channel": channel, "state": new_state}
        except Exception as e:
            return {"channel": channel, "state": -1, "error": str(e)}

    def set_all_relays(self, state: int) -> dict:
        # 批量设置全部 8 路。state 0/1。
        if state not in (0, 1):
            raise ValueError("state must be 0 or 1")
        try:
            self._post("/api/relay/all", {"state": state})
            return {"ok": True, "state": state}
        except Exception as e:
            return {"ok": False, "state": state, "error": str(e)}

    def get_all_relays(self) -> list:
        # 查询全部 8 路状态。
        channels = self._get("/api/state").get("channels", [])
        return [{"channel": i + 1, "state": channels[i]} for i in range(len(channels))]

    def set_wifi(self, ssid: str, password: str) -> str:
        # HTTP 接口不暴露 WiFi 设置
        return "set_wifi not supported in network mode"
