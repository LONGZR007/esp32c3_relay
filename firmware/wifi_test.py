import network
import time

sta = network.WLAN(network.STA_IF)
sta.active(True)

# 尝试设置发射功率（单位 dBm）
# 如果固件支持，这行不会报错；如果不支持会抛出 KeyError/OSError
try:
    sta.config(txpower=15)
    print("TX功率已设置为 8dBm")
except Exception as e:
    print(f"config txpower 不支持: {e}")

time.sleep(1)
sta.connect('long', 'longlong')

timeout = 15
while not sta.isconnected() and timeout > 0:
    time.sleep(1)
    timeout -= 1
    print(".", end="")

print("\n已连接!" if sta.isconnected() else "\n连接超时!")