# WiFi 凭据持久化模块
# 文件 /wifi.cfg 第一行 SSID，第二行 PWD

WIFI_CFG_PATH = '/wifi.cfg'


def load_wifi():
    # 返回 (ssid, pwd)，读不到返回 (None, None)
    try:
        with open(WIFI_CFG_PATH, 'r') as f:
            lines = f.read().splitlines()
    except Exception:
        return (None, None)
    if len(lines) < 2:
        return (None, None)
    ssid = lines[0].strip()
    pwd = lines[1].strip()
    if not ssid:
        return (None, None)
    return (ssid, pwd)


def save_wifi(ssid, pwd):
    # 写入 /wifi.cfg，第一行 SSID，第二行 PWD
    try:
        with open(WIFI_CFG_PATH, 'w') as f:
            f.write(str(ssid) + '\n')
            f.write(str(pwd) + '\n')
    except Exception as e:
        print('[config] save_wifi error:', e)
