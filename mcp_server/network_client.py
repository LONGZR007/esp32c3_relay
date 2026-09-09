# 网络后端：通过 HTTP JSON API 调用 ESP32-C3
# 对外暴露 turn_on_ack / turn_off_ack / toggle / query，返回继电器吸合状态 0/1
import requests
from base_client import BaseClient


class NetworkClient(BaseClient):
    def __init__(self, host: str, http_port: int = 80):
        self.host = host
        self.http_port = http_port
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

    def _set_state(self, channel: int, state: int) -> int:
        # 设置单路并从返回中取出实测吸合状态
        if channel < 1 or channel > 8:
            raise ValueError("channel must be 1-8")
        if state not in (0, 1):
            raise ValueError("state must be 0 or 1")
        resp = self._post("/api/relay", {"ch": channel, "state": state})
        channels = resp.get("channels", [])
        if len(channels) >= channel:
            return int(channels[channel - 1])
        return state

    def _get_state(self, channel: int) -> int:
        # 从整体状态中取出单路吸合状态
        if channel < 1 or channel > 8:
            raise ValueError("channel must be 1-8")
        channels = self._get("/api/state").get("channels", [])
        if len(channels) >= channel:
            return int(channels[channel - 1])
        raise RuntimeError("channel {} not in state response".format(channel))

    def turn_on_ack(self, channel: int) -> int:
        # 继电器吸合（POST state=1），返回实测吸合状态 0/1
        return self._set_state(channel, 1)

    def turn_off_ack(self, channel: int) -> int:
        # 继电器断开（POST state=0），返回实测吸合状态 0/1
        return self._set_state(channel, 0)

    def toggle(self, channel: int) -> int:
        # 翻转继电器：先查询当前状态再取反，返回翻转后状态
        cur = self._get_state(channel)
        new_state = 1 - cur
        return self._set_state(channel, new_state)

    def query(self, channel: int) -> int:
        # 查询继电器状态
        return self._get_state(channel)
