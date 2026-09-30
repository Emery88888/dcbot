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

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'emery888')

PAYMENT_ADDRESSES = {
    'BEP20': '0x3C602BA23061F760F3a86f25698a6696804c2254',
    'TRC20': 'TVDXooB8mC6AD1W68yNLuauQ39cQSJKkQ3'
}

DEFAULT_PROMOS = {
    'VIP888': {'code': 'VIP888', 'type': 'fixed', 'value': 10, 'active': True, 'used_count': 0},
    'OFF10': {'code': 'OFF10', 'type': 'percent', 'value': 10, 'active': True, 'used_count': 0}
}

import urllib.request

UPSTASH_URL = os.environ.get('UPSTASH_REDIS_REST_URL', 'https://warm-wahoo-139691.upstash.io').strip().rstrip('/')
UPSTASH_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN', 'gQAAAAAAAiGrAAIgcDI4NmZiOTliMTRlNmQ0ZmI3ODU4NDkyZWUxMjFmMzVmNA').strip()

def _cloud_get(key):
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return None
    try:
        req = urllib.request.Request(
            f"{UPSTASH_URL}/get/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            raw_val = data.get('result')
            if raw_val:
                return json.loads(raw_val)
    except Exception as e:
        print(f"[Cloud DB Read Error] {e}")
    return None

def _cloud_set(key, val):
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return False
    try:
        val_str = json.dumps(val, ensure_ascii=False)
        req = urllib.request.Request(
            UPSTASH_URL,
            data=json.dumps(["SET", key, val_str]).encode('utf-8'),
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('result') == 'OK'
    except Exception as e:
        print(f"[Cloud DB Write Error] {e}")
    return False

# --- 持久化儲存 ---
def _load_data():
    orders = {}
    promos = dict(DEFAULT_PROMOS)
    tokens = {}

    # 1. 優先從雲端資料庫讀取（永不丟失）
    cloud_data = _cloud_get('dcbot_store')
    if cloud_data and isinstance(cloud_data, dict):
        orders = cloud_data.get('orders', {})
        promos = cloud_data.get('promos', DEFAULT_PROMOS)
        tokens = {o['join_token']: oid for oid, o in orders.items() if 'join_token' in o}
        print(f"[OK] Loaded {len(orders)} orders and {len(promos)} promos from Cloud DB.")
        return orders, promos, tokens

    # 2. 本機檔案備案
    if DATA_FILE.exists():
        try:
            raw = json.loads(DATA_FILE.read_text(encoding='utf-8'))
            orders = raw.get('orders', {})
            promos = raw.get('promos', DEFAULT_PROMOS)
            tokens = {o['join_token']: oid for oid, o in orders.items() if 'join_token' in o}
        except Exception:
            pass
    return orders, promos, tokens

def _save_data():
    with _lock:
        payload = {'orders': ORDERS, 'promos': PROMOS}
        # 存本機
        try:
            DATA_FILE.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception:
            pass
        # 同步存雲端
        if UPSTASH_URL and UPSTASH_TOKEN:
            threading.Thread(target=_cloud_set, args=('dcbot_store', payload), daemon=True).start()

ORDERS, PROMOS, JOIN_TOKENS = _load_data()

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
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Admin-Token')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Admin-Token')
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

    def _check_admin_auth(self):
        auth = self.headers.get('Authorization', '')
        token = self.headers.get('X-Admin-Token', '')
        if auth.startswith('Bearer '):
            token = auth[7:].strip()
        return token == ADMIN_PASSWORD

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

        # 1. 管理員登入
        if parsed.path == '/api/admin/login':
            data, error = self._parse_json_body()
            if error or not isinstance(data, dict):
                self._send_json(400, {'ok': False, 'message': '請求格式錯誤'})
                return
            pwd = str(data.get('password', '')).strip()
            if pwd == ADMIN_PASSWORD:
                self._send_json(200, {'ok': True, 'token': ADMIN_PASSWORD, 'message': '登入成功'})
            else:
                self._send_json(401, {'ok': False, 'message': '管理員密碼錯誤'})
            return

        # 2. 優惠碼即時驗證 (公開給前端)
        if parsed.path == '/api/promo/verify':
            data, error = self._parse_json_body()
            if error or not isinstance(data, dict):
                self._send_json(400, {'ok': False, 'message': '格式錯誤'})
                return
            code = str(data.get('code', '')).strip().upper()
            amount = float(data.get('amount', 0))
            if not code:
                self._send_json(400, {'ok': False, 'message': '請提供優惠碼'})
                return
            promo = PROMOS.get(code)
            if not promo or not promo.get('active', True):
                self._send_json(200, {'ok': True, 'valid': False, 'message': '優惠碼不存在或已停用'})
                return
            p_type = promo.get('type', 'fixed')
            p_val = float(promo.get('value', 0))
            if p_type == 'percent':
                discount = round(amount * (p_val / 100.0), 2)
                msg = f'優惠碼已套用！享 {p_val}% 折扣 (折抵 {discount}U)'
            else:
                discount = min(amount, p_val)
                msg = f'優惠碼已套用！現折 {discount}U'
            final_amount = max(0.0, amount - discount)
            self._send_json(200, {
                'ok': True,
                'valid': True,
                'code': code,
                'discount': discount,
                'final_amount': final_amount,
                'message': msg
            })
            return

        # 3. 管理員：更新訂單審核狀態
        if parsed.path.startswith('/api/admin/orders/') and parsed.path.endswith('/status'):
            if not self._check_admin_auth():
                self._send_json(401, {'ok': False, 'message': '未授權'})
                return
            parts = [p for p in parsed.path.split('/') if p]
            if len(parts) >= 4:
                order_id = parts[3]
                order = ORDERS.get(order_id)
                if not order:
                    self._send_json(404, {'ok': False, 'message': '找不到此訂單'})
                    return
                data, _ = self._parse_json_body()
                status = str(data.get('status', '')).strip()
                if status in ['pending', 'approved', 'rejected']:
                    order['status'] = status
                    _save_data()
                    self._send_json(200, {'ok': True, 'message': '狀態已更新', 'order': order})
                    return
                self._send_json(400, {'ok': False, 'message': '無效的狀態'})
                return

        # 4. 管理員：優惠碼管理 (新增/啟用/停用/刪除)
        if parsed.path == '/api/admin/promos':
            if not self._check_admin_auth():
                self._send_json(401, {'ok': False, 'message': '未授權'})
                return
            data, error = self._parse_json_body()
            if error or not isinstance(data, dict):
                self._send_json(400, {'ok': False, 'message': '請求格式錯誤'})
                return
            action = data.get('action', 'create')
            code = str(data.get('code', '')).strip().upper()
            if not code:
                self._send_json(400, {'ok': False, 'message': '代碼不能為空'})
                return
            if action == 'create':
                p_type = str(data.get('type', 'fixed'))
                p_val = float(data.get('value', 10))
                PROMOS[code] = {
                    'code': code,
                    'type': p_type,
                    'value': p_val,
                    'active': True,
                    'used_count': 0
                }
                _save_data()
                self._send_json(200, {'ok': True, 'message': f'優惠碼 {code} 已建立', 'promos': list(PROMOS.values())})
                return
            elif action == 'toggle':
                if code in PROMOS:
                    PROMOS[code]['active'] = not PROMOS[code].get('active', True)
                    _save_data()
                    self._send_json(200, {'ok': True, 'message': '狀態已切換', 'promos': list(PROMOS.values())})
                    return
                self._send_json(404, {'ok': False, 'message': '優惠碼不存在'})
                return
            elif action == 'delete':
                if code in PROMOS:
                    del PROMOS[code]
                    _save_data()
                    self._send_json(200, {'ok': True, 'message': f'優惠碼 {code} 已刪除', 'promos': list(PROMOS.values())})
                    return
                self._send_json(404, {'ok': False, 'message': '優惠碼不存在'})
                return

        # 5. 建立訂單 (用戶前端提交)
        if parsed.path == '/api/orders':
            data, error = self._parse_json_body()
            if error or not isinstance(data, dict):
                self._send_json(400, {'ok': False, 'message': 'Invalid JSON payload'})
                return

            name = str(data.get('name', '')).strip()
            contact = str(data.get('contact', '')).strip()
            plan = str(data.get('plan', '1M')).strip()
            group = str(data.get('group', 'https://discord.gg/JvFTfFY5KZ')).strip() or 'https://discord.gg/JvFTfFY5KZ'
            network = str(data.get('network', 'BEP20')).strip().upper() or 'BEP20'
            quantity = int(data.get('quantity') or 1)
            screenshot = str(data.get('screenshot', '')).strip()
            referral = str(data.get('referral', '')).strip().upper()

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

            subtotal = base_amount * quantity
            discount = 0.0

            # 套用優惠碼
            if referral and referral in PROMOS and PROMOS[referral].get('active', True):
                promo = PROMOS[referral]
                p_type = promo.get('type', 'fixed')
                p_val = float(promo.get('value', 0))
                if p_type == 'percent':
                    discount = round(subtotal * (p_val / 100.0), 2)
                else:
                    discount = min(float(subtotal), p_val)
                promo['used_count'] = promo.get('used_count', 0) + 1

            amount = max(0.0, subtotal - discount)

            if not name:
                self._send_json(400, {'ok': False, 'message': '請填寫付款人名稱'})
                return
            if network not in PAYMENT_ADDRESSES:
                self._send_json(400, {'ok': False, 'message': '不支援的付款網路'})
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
                'subtotal': subtotal,
                'discount': discount,
                'amount': amount,
                'address': PAYMENT_ADDRESSES[network],
                'status': 'pending',
                'created_at': int(time.time()),
                'join_token': join_token,
                'used': False,
                'referral': referral if discount > 0 else '',
                'screenshot': screenshot
            }

            ORDERS[order_id] = order
            JOIN_TOKENS[join_token] = order_id
            _save_data()

            host = self.headers.get('Host', '127.0.0.1:8001')
            scheme = 'https' if not host.startswith('127') else 'http'
            join_link = f'{scheme}://{host}/api/join/{order_id}/{join_token}'

            self._send_json(200, {
                'ok': True,
                'message': '訂單已建立，等待管理員審核。',
                'order_id': order_id,
                'payment_network': network,
                'payment_address': order['address'],
                'amount': amount,
                'join_link': join_link,
                'status': 'pending'
            })
            return

        self._send_json(404, {'ok': False, 'message': 'Not found'})

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == '/api/health':
            self._send_json(200, {'ok': True, 'message': 'ready'})
            return

        # 管理員 API：獲取所有訂單
        if parsed.path == '/api/admin/orders':
            if not self._check_admin_auth():
                self._send_json(401, {'ok': False, 'message': '未授權'})
                return
            order_list = sorted(list(ORDERS.values()), key=lambda x: x.get('created_at', 0), reverse=True)
            self._send_json(200, {'ok': True, 'orders': order_list})
            return

        # 管理員 API：獲取所有優惠碼
        if parsed.path == '/api/admin/promos':
            if not self._check_admin_auth():
                self._send_json(401, {'ok': False, 'message': '未授權'})
                return
            self._send_json(200, {'ok': True, 'promos': list(PROMOS.values())})
            return

        # 導向 /admin 到 admin.html
        if parsed.path == '/admin':
            self.path = '/admin.html'

        # 查詢單一訂單狀態
        if parsed.path.startswith('/api/orders/'):
            parts = [p for p in parsed.path.split('/') if p]
            if len(parts) >= 3 and parts[0] == 'api' and parts[1] == 'orders':
                order_id = parts[2]
                order = ORDERS.get(order_id)
                if not order:
                    self._send_json(404, {'ok': False, 'message': 'Order not found'})
                    return
                self._send_json(200, {'ok': True, 'order': order})
                return

        return super().do_GET()

if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 8001))
    IS_CLOUD = 'PORT' in os.environ

    if not IS_CLOUD:
        import socket
        import sys
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.settimeout(1)
        result = test_sock.connect_ex(('127.0.0.1', PORT))
        test_sock.close()
        if result == 0:
            print('[ERROR] Port ' + str(PORT) + ' already in use.')
            sys.exit(1)

        print('=' * 50)
        print('[OK] Server started (local)')
        print(f'     Web:   http://127.0.0.1:{PORT}')
        print(f'     Admin: http://127.0.0.1:{PORT}/admin.html')
        print('=' * 50)
    else:
        print('[OK] Server started on cloud, port ' + str(PORT))

    server = ThreadingHTTPServer(('0.0.0.0', PORT), ApiHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[STOP] Server stopped.')
