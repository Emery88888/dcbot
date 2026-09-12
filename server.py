from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import uuid
import time
import os
import threading
from pathlib import Path

ROOT = Path.cwd()
DATA_FILE = ROOT / 'orders.json'
_lock = threading.Lock()

PAYMENT_ADDRESSES = {
    'BEP20': '0x3C602BA23061F760F3a86f25698a6696804c2254',
    'TRC20': 'TVDXooB8mC6AD1W68yNLuauQ39cQSJKkQ3'
}

# --- 持久化：從檔案載入訂單 ---
def _load_data():
    if DATA_FILE.exists():
        try:
            raw = json.loads(DATA_FILE.read_text(encoding='utf-8'))
            orders = raw.get('orders', {})
            tokens = {o['join_token']: oid for oid, o in orders.items() if 'join_token' in o}
            return orders, tokens
        except Exception:
            pass
    return {}, {}

def _save_data():
    with _lock:
        DATA_FILE.write_text(
            json.dumps({'orders': ORDERS}, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

ORDERS, JOIN_TOKENS = _load_data()

class ApiHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _send_html(self, status, html):
        body = html.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _join_page_html(self, order):
        return f"""
<!doctype html>
<html lang=\"zh-Hant\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>付款驗證成功</title>
  <style>
    :root {{
      --bg: #07111f;
      --panel: #101b2c;
      --line: rgba(230, 244, 255, 0.12);
      --text: #eef8ff;
      --muted: #b2bfd5;
      --green: #8affb4;
      --blue: #70f3ff;
      --shadow: rgba(0, 0, 0, 0.3);
      --font: \"Inter\", \"Segoe UI\", \"PingFang TC\", \"Microsoft JhengHei\", Arial, sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: var(--font);
      color: var(--text);
      background: radial-gradient(circle at 70% 10%, rgba(33, 111, 216, 0.4), transparent 30%), var(--bg);
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .shell {{
      width: min(680px, calc(100vw - 32px));
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: 0 24px 80px var(--shadow);
      padding: 28px;
      position: relative;
      overflow: hidden;
    }}
    .shell::before {{
      content: \"\";
      position: absolute;
      width: 140px;
      height: 140px;
      border-radius: 50%;
      border: 1px solid var(--blue);
      left: -40px;
      top: -40px;
      filter: blur(12px);
    }}
    .kicker {{
      font-size: 12px;
      font-weight: 900;
      letter-spacing: 0.2em;
      color: var(--blue);
      text-transform: uppercase;
    }}
    h1 {{
      margin: 10px 0 12px;
      font-size: clamp(34px, 4vw, 50px);
      line-height: 1.2;
    }}
    .message {{
      color: var(--muted);
      font-size: 16px;
      line-height: 1.7;
    }}
    .card {{
      margin-top: 20px;
      border-radius: 14px;
      border: 1px solid var(--line);
      padding: 16px;
      background: rgba(20, 31, 53, .72);
    }}
    .card-row {{
      color: var(--muted);
      font-size: 14px;
      margin: 8px 0;
    }}
    .card-row b {{ color: var(--text); }}
    .join-btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 48px;
      padding: 0 26px;
      margin-top: 14px;
      border-radius: 12px;
      border: 1px solid var(--green);
      background: linear-gradient(135deg, var(--green), var(--blue));
      color: var(--panel);
      font-weight: 900;
      text-decoration: none;
    }}
  </style>
</head>
<body>
  <main class=\"shell\">
    <div class=\"kicker\">付款驗證</div>
    <h1>歡迎加入 DC 群</h1>
    <div class=\"message\">付款資料已完成驗證，請點擊下方連結進入群組。</div>
    <section class=\"card\">
      <div class=\"card-row\"><b>訂單：</b>{order['order_id']}</div>
      <div class=\"card-row\"><b>方案：</b>{order['plan']}</div>
      <div class=\"card-row\"><b>網路：</b>{order['network']}</div>
      <div class=\"card-row\"><b>群組：</b>{order['group']}</div>
      <a class="join-btn" href="{order['group']}">進入群組</a>
    </section>
  </main>
</body>
</html>
"""

    def _parse_json_body(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            raw = self.rfile.read(length)
            if not raw:
                return None, 'Invalid JSON payload'
            return json.loads(raw.decode('utf-8')), None
        except Exception:
            return None, 'Invalid JSON payload'

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/orders':
            self._send_json(404, {'ok': False, 'message': 'Not found'})
            return

        data, error = self._parse_json_body()
        if error:
            self._send_json(400, {'ok': False, 'message': error})
            return
        if not isinstance(data, dict):
            self._send_json(400, {'ok': False, 'message': 'Invalid JSON payload'})
            return

        name = str(data.get('name', '')).strip()
        contact = str(data.get('contact', '')).strip()
        plan = str(data.get('plan', '1M')).strip()
        group = str(data.get('group', 'https://discord.gg/JvFTfFY5KZ')).strip() or 'https://discord.gg/JvFTfFY5KZ'
        network = str(data.get('network', 'BEP20')).strip().upper() or 'BEP20'
        quantity = int(data.get('quantity') or 1)
        if quantity < 1 or quantity > 20:
            self._send_json(400, {'ok': False, 'message': 'Quantity must be between 1 and 20'})
            return

        if plan == '1Y':
            if quantity > 2:
                self._send_json(400, {'ok': False, 'message': '1Y plan quantity must be between 1 and 2'})
                return
            base_amount = 1188
        elif plan == '1M':
            base_amount = 99
        else:
            self._send_json(400, {'ok': False, 'message': 'Unsupported plan'})
            return

        amount = base_amount * quantity

        if not name:
            self._send_json(400, {'ok': False, 'message': 'Missing required fields'})
            return
        if network not in PAYMENT_ADDRESSES:
            self._send_json(400, {'ok': False, 'message': 'Unsupported payment network'})
            return
        if amount <= 0:
            self._send_json(400, {'ok': False, 'message': 'Invalid payment amount'})
            return

        order_id = 'DX' + str(uuid.uuid4())[:8].upper()
        join_token = str(uuid.uuid4())

        order = {
            'order_id': order_id,
            'name': name,
            'contact': contact,
            'plan': plan,
            'quantity': quantity,
            'group': group,
            'network': network,
            'amount': amount,
            'address': PAYMENT_ADDRESSES[network],
            'status': 'pending',
            'created_at': int(time.time()),
            'join_token': join_token,
            'used': False
        }

        ORDERS[order_id] = order
        JOIN_TOKENS[join_token] = order_id
        _save_data()

        # 動態取得 host，部署到雲端時也能正確產生連結
        host = self.headers.get('Host', '127.0.0.1:8001')
        scheme = 'https' if not host.startswith('127') else 'http'
        join_link = f'{scheme}://{host}/api/join/{order_id}/{join_token}'

        self._send_json(200, {
            'ok': True,
            'message': 'Order created. Waiting for payment confirmation.',
            'order_id': order_id,
            'payment_network': network,
            'payment_address': order['address'],
            'amount': amount,
            'join_link': join_link,
            'group_invite_url': group,
            'expires_at': int(time.time()) + 3600,
            'status': 'pending'
        })

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/api/health':
            self._send_json(200, {'ok': True, 'message': 'local api ready'})
            return

        # GET /api/join/<order_id>/<token>
        if parsed.path.startswith('/api/join/'):
            parts = [p for p in parsed.path.split('/') if p]
            if len(parts) == 4 and parts[0] == 'api' and parts[1] == 'join':
                order_id = parts[2]
                token = parts[3]
                order = ORDERS.get(order_id)
                if not order:
                    self._send_html(404, '<html><body><h1>Order not found</h1></body></html>')
                    return
                if order.get('join_token') != token:
                    self._send_html(403, '<html><body><h1>Invalid one-time token</h1></body></html>')
                    return
                if order.get('used'):
                    self._send_html(410, '<html><body><h1>One-time link has been used</h1></body></html>')
                    return

                order['status'] = 'paid'
                order['used'] = True
                _save_data()
                self._send_html(200, self._join_page_html(order))
                return

        # query order status by id with optional contact checking
        if parsed.path.startswith('/api/orders/'):
            parts = [p for p in parsed.path.split('/') if p]
            if len(parts) >= 3 and parts[0] == 'api' and parts[1] == 'orders':
                order_id = parts[2]
                order = ORDERS.get(order_id)
                if not order:
                    self._send_json(404, {'ok': False, 'message': 'Order not found'})
                    return

                query = parse_qs(parsed.query)
                contact = (query.get('contact') or [''])[0].strip().lower()
                if contact and order.get('contact', '').strip().lower() != contact:
                    self._send_json(403, {'ok': False, 'message': 'Contact mismatch'})
                    return

                self._send_json(200, {
                    'ok': True,
                    'message': 'Order found',
                    'order': {
                        'order_id': order['order_id'],
                        'name': order['name'],
                        'contact': order['contact'],
                        'plan': order['plan'],
                        'group': order['group'],
                        'network': order['network'],
                        'amount': order['amount'],
                        'address': order['address'],
                        'status': order['status'],
                        'created_at': order['created_at'],
                        'used': bool(order.get('used'))
                    }
                })
                return

        return super().do_GET()

if __name__ == '__main__':
    import socket
    import sys

    PORT = int(os.environ.get('PORT', 8001))
    IS_CLOUD = 'PORT' in os.environ  # Railway/Render 會設定 PORT 環境變數

    if not IS_CLOUD:
        # 本機防止重複啟動
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.settimeout(1)
        result = test_sock.connect_ex(('127.0.0.1', PORT))
        test_sock.close()
        if result == 0:
            print('[ERROR] Port ' + str(PORT) + ' already in use. Server is already running!')
            print('        To restart, close the existing server window first.')
            sys.exit(1)

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = 'your-ip'

        print('=' * 50)
        print('[OK] Server started (local)')
        print('     Local:   http://127.0.0.1:' + str(PORT))
        print('     Network: http://' + local_ip + ':' + str(PORT))
        print('     Press Ctrl+C to stop')
        print('=' * 50)
    else:
        print('[OK] Server started on Railway, port ' + str(PORT))

    server = ThreadingHTTPServer(('0.0.0.0', PORT), ApiHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[STOP] Server stopped.')


