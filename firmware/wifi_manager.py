# WiFi 连接管理模块
# 无凭据启动 AP，有凭据连 STA，断线重连

import time
import config


def _start_ap():
    # 启动开放 AP 模式
    import network
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    try:
        ap.config(essid='ESP32C3-Relay', password='')
    except Exception:
        # 部分固件不接受空密码，退回仅设 essid
        try:
            ap.config(essid='ESP32C3-Relay')
        except Exception as e:
            print('[wifi] AP config error:', e)
    print('[wifi] AP started: ESP32C3-Relay')


def connect_loop():
    # 无限重连主循环
    while True:
        try:
            ssid, pwd = config.load_wifi()
            if ssid is None:
                # 无凭据，启动 AP，等待用户配置
                _start_ap()
                time.sleep(30)
                continue
            import network
            sta = network.WLAN(network.STA_IF)
            sta.active(True)
            sta.connect(ssid, pwd)
            # 等待最多 5 秒
            connected = False
            for _ in range(50):
                if sta.isconnected():
                    connected = True
                    break
                time.sleep(0.1)
            if connected:
                print('[wifi] connected, IP:', sta.ifconfig())
                # 监测循环，断线则回到外层重连
                while True:
                    if not sta.isconnected():
                        print('[wifi] disconnected, reconnecting')
                        break
                    time.sleep(5)
                continue
            else:
                # 5 秒连不上，启动 AP 重试
                print('[wifi] connect failed, starting AP')
                _start_ap()
                time.sleep(30)
                continue
        except Exception as e:
            print('[wifi] error:', e)
            time.sleep(5)
