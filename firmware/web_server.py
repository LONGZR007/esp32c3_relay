# 最小 HTTP 服务模块（原生 socket）
# 监听 80，提供继电器状态查询与控制 REST API
# 说明：ESP32-C3 单核上 _thread 中阻塞 accept() 不可靠，
#       故本模块提供 poll_server()，由主循环用 select 非阻塞轮询。

import socket
import json
import select

from relay import relays


def _send(conn, status_line, body=b'', content_type='application/json'):
    # 统一发送响应，含 CORS 头与 Content-Length
    headers = (
        'HTTP/1.1 ' + status_line + '\r\n'
        'Content-Type: ' + content_type + '\r\n'
        'Content-Length: ' + str(len(body)) + '\r\n'
        'Access-Control-Allow-Origin: *\r\n'
        'Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n'
        'Access-Control-Allow-Headers: Content-Type\r\n'
        'Connection: close\r\n'
        '\r\n'
    )
    try:
        conn.send(headers.encode('utf-8') + body)
    except Exception as e:
        print('[web] send error:', e)


def _handle_request(conn):
    try:
        # 读请求行 + headers，直到空行
        data = b''
        while b'\r\n\r\n' not in data:
            chunk = conn.recv(1024)
            if not chunk:
                return
            data += chunk
            if len(data) > 4096:
                break
        header_part, _, body_part = data.partition(b'\r\n\r\n')
        lines = header_part.split(b'\r\n')
        request_line = lines[0].decode('utf-8', 'ignore') if lines else ''
        parts = request_line.split(' ')
        method = parts[0] if len(parts) > 0 else ''
        path = parts[1] if len(parts) > 1 else ''
        # 解析 Content-Length
        content_length = 0
        for line in lines[1:]:
            if b':' in line:
                k, _, v = line.partition(b':')
                if k.strip().lower() == b'content-length':
                    try:
                        content_length = int(v.strip())
                    except Exception:
                        content_length = 0
        # 读完整 body
        body = body_part
        while len(body) < content_length:
            chunk = conn.recv(1024)
            if not chunk:
                break
            body += chunk
        body = body[:content_length]

        # 路由分发
        if method == 'OPTIONS':
            _send(conn, '204 No Content', b'')
            return

        if method == 'GET' and path == '/':
            try:
                with open('index.html', 'rb') as f:
                    body_out = f.read()
            except Exception:
                _send(conn, '404 Not Found', b'{"error":"index not found"}')
                return
            _send(conn, '200 OK', body_out, 'text/html; charset=utf-8')
            return

        if method == 'GET' and path == '/api/state':
            body_out = json.dumps({'channels': relays.get_all()}).encode('utf-8')
            _send(conn, '200 OK', body_out)
            return

        if method == 'POST' and path == '/api/relay':
            try:
                req = json.loads(body.decode('utf-8', 'ignore'))
                ch = int(req.get('ch'))
                state = int(req.get('state'))
            except Exception:
                _send(conn, '400 Bad Request', b'{"error":"bad request"}')
                return
            if ch < 1 or ch > 8:
                _send(conn, '400 Bad Request', b'{"error":"channel out of range"}')
                return
            try:
                relays.set(ch, state)
            except Exception:
                _send(conn, '400 Bad Request', b'{"error":"bad request"}')
                return
            body_out = json.dumps({'channels': relays.get_all()}).encode('utf-8')
            _send(conn, '200 OK', body_out)
            return

        if method == 'POST' and path == '/api/relay/all':
            try:
                req = json.loads(body.decode('utf-8', 'ignore'))
                state = int(req.get('state'))
            except Exception:
                _send(conn, '400 Bad Request', b'{"error":"bad request"}')
                return
            try:
                relays.set_all(state)
            except Exception:
                _send(conn, '400 Bad Request', b'{"error":"bad request"}')
                return
            body_out = json.dumps({'channels': relays.get_all()}).encode('utf-8')
            _send(conn, '200 OK', body_out)
            return

        # 其他路径
        _send(conn, '404 Not Found', b'{"error":"not found"}')
    except Exception as e:
        print('[web] handle error:', e)
        try:
            _send(conn, '500 Internal Server Error', b'{"error":"server error"}')
        except Exception:
            pass


_listen = None
_listen_err_time = 0


def poll_server():
    # 由主循环周期调用：初始化监听 socket（首次），并处理当前已到达的连接。
    # select 非阻塞，无连接时立即返回，不会卡住主循环。
    global _listen, _listen_err_time
    import time
    if _listen is None:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('0.0.0.0', 80))
            s.listen(5)
            _listen = s
            print('[web] server listening on :80')
        except Exception as e:
            # 启动失败（如端口占用），限制重试频率避免刷屏
            now = time.ticks_ms()
            if now - _listen_err_time > 5000:
                print('[web] listen error:', e)
                _listen_err_time = now
            return
    try:
        r, _, _ = select.select([_listen], [], [], 0)
    except Exception:
        return
    if not r:
        return
    for _ in range(3):  # 单次最多处理 3 个连接，避免长时间独占主循环
        try:
            conn, addr = _listen.accept()
        except Exception:
            break
        try:
            conn.settimeout(3)
            _handle_request(conn)
        except Exception as e:
            print('[web] handle error:', e)
        try:
            conn.close()
        except Exception:
            pass
