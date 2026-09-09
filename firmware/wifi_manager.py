# WiFi 连接管理模块
# 无凭据启动 AP，有凭据连 STA，断线重连
# GPIO8 作 WiFi 指示灯：连上点亮(高)，未连/断线熄灭(低)

import time
import machine
import config

# WiFi 指示灯：GPIO8，高电平点亮
led = machine.Pin(8, machine.Pin.OUT, value=0)


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
            # 每次尝试连接/重试前，指示灯熄灭（连上后再点亮）
            led.value(0)
            ssid, pwd = config.load_wifi()
            if ssid is None:
                # 无凭据，启动 AP，等待用户配置
                _start_ap()
                time.sleep(30)
                continue
            import network
            sta = network.WLAN(network.STA_IF)
            if not sta.active():
                sta.active(True)
                time.sleep(0.5)
            try:
                sta.connect(ssid, pwd)
            except Exception as e:
                print('[wifi] connect error:', e)
                # 无线驱动内部状态错误：重置接口后慢速重试，避免高频轰击驱动
                try:
                    sta.active(False)
                except Exception:
                    pass
                time.sleep(3)
                continue
            # 等待最多 5 秒
            connected = False
            for _ in range(50):
                if sta.isconnected():
                    connected = True
                    break
                time.sleep(0.1)
            if connected:
                print('[wifi] connected, IP:', sta.ifconfig())
                # STA 已连上，若之前开过 AP 则关闭，避免 STA+AP 双模式
                try:
                    ap = network.WLAN(network.AP_IF)
                    if ap.active():
                        ap.active(False)
                        print('[wifi] AP stopped')
                except Exception:
                    pass
                # WiFi 指示灯点亮
                led.value(1)
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
