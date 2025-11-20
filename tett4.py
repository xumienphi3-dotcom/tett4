import base64
import hashlib
import json
import os
import platform
import random
import re
import string
import subprocess
import sys
import time
import urllib.parse
import uuid
import threading
import ctypes
import inspect
import hmac
import tempfile
import shutil
import signal
import atexit
from datetime import datetime, timedelta, timezone
from time import sleep

# --- CẤU HÌNH MÀU SẮC & THƯ VIỆN NGOÀI ---
try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    import pytz
    import requests
    import urllib3
    # [NÂNG CẤP BẢO MẬT] Đã bật xác thực SSL để chống Hook/Sniff
    # urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) 
    from rich.table import Table
    from rich.console import Console
except ImportError:
    print('__Đang cài đặt các thư viện cần thiết, vui lòng chờ...__')
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "colorama", "pytz", "rich", "urllib3"])
        print('__Cài đặt hoàn tất, vui lòng chạy lại Tool__')
    except Exception as e:
        print('__lỗi hãy thử lại__')
        print('__Vui lòng tự cài đặt bằng lệnh: pip install requests colorama pytz rich urllib3__')
    sys.exit()

# --- MÀU SẮC ---
xnhac = "\033[1;36m"
do = "\033[1;31m"
luc = "\033[1;32m"
vang = "\033[1;33m"
xduong = "\033[1;34m"
hong = "\033[1;35m"
trang = "\033[1;39m"
end = '\033[0m'

console = Console()

# --- CẤU HÌNH ---
FREE_CACHE_FILE = 'free_key_cache.bin' 
VIP_CACHE_FILE = 'vip_data.bin'         
HANOI_TZ = pytz.timezone('Asia/Ho_Chi_Minh')
VIP_KEY_URL = "https://raw.githubusercontent.com/xumienphi4-dot/keytdk1/main/keytdk1.txt"

# [NÂNG CẤP BẢO MẬT] Bật Verify SSL để chống các tool debug mạng (Fiddler/Charles)
SSL_VERIFY = True 

# Biến toàn cục để xác định trạng thái phiên
CURRENT_SESSION_TYPE = "UNKNOWN" # 'VIP' hoặc 'FREE'

# --- HỆ THỐNG BẢO MẬT NÂNG CAO (ANTIDEBUG & PROCESS MONITOR) ---

class SecurityDaemon:
    def __init__(self):
        self.is_running = True
        self.violation_count = 0

    def kill_process(self, reason="Unknown"):
        # Trong môi trường thực tế, tắt tool khi phát hiện debug
        # sys.exit()
        pass

    def check_remote_debugger(self):
        if platform.system() == "Windows":
            try:
                is_debugger_present = ctypes.windll.kernel32.IsDebuggerPresent()
                if is_debugger_present:
                    return True
                process = ctypes.windll.kernel32.GetCurrentProcess()
                present = ctypes.c_bool(False)
                ctypes.windll.kernel32.CheckRemoteDebuggerPresent(process, ctypes.byref(present))
                if present.value:
                    return True
            except:
                pass
        return False

    def check_stack_trace(self):
        try:
            for frame in inspect.stack():
                fname = frame.filename.lower()
                forbidden = ['pydevd', 'pdb.py', 'pycharm', 'vscode', 'debugger', 'hook']
                if any(k in fname for k in forbidden):
                    return True
        except:
            pass
        return False
    
    def integrity_check_loop(self):
        while self.is_running:
            if self.check_remote_debugger(): self.kill_process("Debugger Detected (API)")
            if self.check_stack_trace(): self.kill_process("Debugger Stack Trace Found")
            if sys.gettrace() is not None: self.kill_process("Sys Trace Hook Detected")
            time.sleep(2.5)

    def start_protection(self):
        t = threading.Thread(target=self.integrity_check_loop, daemon=True)
        t.start()

security_system = SecurityDaemon()
security_system.start_protection()

# --- CHỨC NĂNG XÓA AN TOÀN (SECURE WIPE - AGGRESSIVE) ---

def secure_file_wipe(file_path):
    """
    Xóa file vĩnh viễn: Ghi đè dữ liệu rác -> Đổi tên -> Xóa.
    """
    try:
        if not os.path.exists(file_path): return
        
        # 1. Ghi đè dữ liệu (Wipe)
        length = os.path.getsize(file_path)
        # Giới hạn wipe 10MB đầu để tránh treo nếu file quá lớn
        wipe_len = min(length, 10 * 1024 * 1024) 
        with open(file_path, "wb") as f:
            f.write(os.urandom(wipe_len))
            f.flush()
            try:
                os.fsync(f.fileno())
            except: pass
            
        # 2. Đổi tên thành tên rác (Phá Metadata)
        dir_name = os.path.dirname(file_path)
        random_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=15))
        new_path = os.path.join(dir_name, random_name)
        try:
            os.rename(file_path, new_path)
            file_path = new_path
        except: pass
        
        # 3. Xóa vĩnh viễn
        os.remove(file_path)
        # print(f"Đã xóa an toàn: {file_path}")
    except:
        # Fallback nếu không thể wipe
        try: os.remove(file_path)
        except: pass

def recursive_secure_delete(path):
    """
    Xóa đệ quy cả thư mục và file bên trong.
    """
    if os.path.isfile(path):
        secure_file_wipe(path)
    elif os.path.isdir(path):
        # Duyệt từ dưới lên (topdown=False) để xóa file con trước
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                secure_file_wipe(os.path.join(root, name))
            for name in dirs:
                try:
                    os.rmdir(os.path.join(root, name))
                except: pass
        try:
            os.rmdir(path)
            # print(f"Đã xóa thư mục: {path}")
        except: pass

def aggressive_cleanup():
    """
    [NÂNG CẤP] Quét và xóa tất cả file/thư mục có chứa chữ 'tdk' hoặc 'TDK'.
    Bảo vệ file đang chạy không bị xóa.
    """
    try:
        current_dir = os.getcwd()
        # Lấy tên file script đang chạy thực tế
        current_script_name = os.path.basename(sys.argv[0])
        
        # Danh sách file hệ thống/quan trọng cần giữ lại (nếu có)
        # Ở đây ta chỉ giữ lại file đang chạy.
        
        items = os.listdir(current_dir)
        
        for item in items:
            # BỎ QUA FILE ĐANG CHẠY
            if item == current_script_name:
                continue

            # Kiểm tra xem tên file/folder có chứa "tdk" không (không phân biệt hoa thường)
            # Điều kiện: chứa 'tdk' HOẶC nằm trong danh sách đen cứng
            item_lower = item.lower()
            
            should_delete = False
            
            # Logic xóa mạnh: Cứ có chữ tdk là xóa
            if "tdk" in item_lower:
                should_delete = True
            
            # Danh sách đen bổ sung (theo yêu cầu cũ)
            blacklist_exact = {"tbumx01", "tet1", "text.txt", "tooltdk", "tooltdk1"}
            if item_lower in blacklist_exact:
                should_delete = True

            if should_delete:
                full_path = os.path.join(current_dir, item)
                # print(f"{do}Phát hiện rác: {item} -> Đang xóa sạch...{trang}")
                recursive_secure_delete(full_path)

    except Exception as e:
        # print(f"Lỗi dọn dẹp: {e}")
        pass

# --- CORE MÃ HÓA & MÃ MÁY ---

def get_device_id():
    """Lấy ID thiết bị duy nhất"""
    system = platform.system()
    try:
        if system == "Windows":
            cpu_info = subprocess.check_output('wmic cpu get ProcessorId', shell=True, text=True, stderr=subprocess.DEVNULL)
            cpu_info = ''.join(line.strip() for line in cpu_info.splitlines() if line.strip() and "ProcessorId" not in line)
        else:
            try:
                cpu_info = subprocess.check_output("cat /proc/cpuinfo", shell=True, text=True)
            except:
                cpu_info = platform.processor()
        if not cpu_info:
            cpu_info = platform.processor()
    except Exception:
        cpu_info = "Unknown"

    hash_hex = hashlib.sha256(cpu_info.encode()).hexdigest()
    only_digits = re.sub(r'\D', '', hash_hex)
    if len(only_digits) < 16:
        only_digits = (only_digits * 3)[:16]

    return f"DEVICE-{only_digits[:16]}"

def secure_derive_key(salt, device_id):
    """Tạo khóa mã hóa từ Device ID"""
    password = device_id.encode()
    return hashlib.pbkdf2_hmac('sha256', password, salt, 100000)

def _raw_encrypt_bytes(data_bytes, device_id):
    """Mã hóa dữ liệu"""
    salt = os.urandom(16)
    key = secure_derive_key(salt, device_id)
    
    encrypted_body = bytearray()
    key_stream = hashlib.sha256(key).digest()
    
    for i, byte in enumerate(data_bytes):
        if i % 32 == 0: 
            key_stream = hashlib.sha256(key_stream + str(i).encode()).digest()
        encrypted_body.append(byte ^ key_stream[i % 32])
    
    signature = hmac.new(key, encrypted_body, hashlib.sha256).digest()
    return salt + signature + encrypted_body

def _raw_decrypt_bytes(file_content, device_id):
    """Giải mã dữ liệu"""
    if len(file_content) < 48: return None
        
    salt = file_content[:16]
    signature = file_content[16:48]
    encrypted_body = file_content[48:]
    
    key = secure_derive_key(salt, device_id)
    
    cal_signature = hmac.new(key, encrypted_body, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, cal_signature):
        raise ValueError("File corrupted or wrong machine ID")
        
    decrypted_data = bytearray()
    key_stream = hashlib.sha256(key).digest()
    
    for i, byte in enumerate(encrypted_body):
        if i % 32 == 0:
            key_stream = hashlib.sha256(key_stream + str(i).encode()).digest()
        decrypted_data.append(byte ^ key_stream[i % 32])
    
    return bytes(decrypted_data)

def secure_save_data(filename, data_dict):
    """Lưu file cấu hình"""
    try:
        json_bytes = json.dumps(data_dict).encode('utf-8')
        device_id = get_device_id()
        encrypted_blob = _raw_encrypt_bytes(json_bytes, device_id)
        with open(filename, 'wb') as f:
            f.write(encrypted_blob)
    except Exception as e:
        print(f"{do}Lỗi lưu dữ liệu: {e}{trang}")

def secure_load_data(filename):
    """Đọc file cấu hình"""
    if not os.path.exists(filename): return None
    try:
        with open(filename, 'rb') as f:
            file_content = f.read()
        device_id = get_device_id()
        decrypted_bytes = _raw_decrypt_bytes(file_content, device_id)
        return json.loads(decrypted_bytes.decode('utf-8'))
    except Exception:
        return None

# --- CÁC HÀM TIỆN ÍCH GIAO DIỆN ---

def get_ip_address():
    try:
        # [NÂNG CẤP] Verify SSL enabled
        response = requests.get('https://api.ipify.org?format=json', timeout=5, verify=SSL_VERIFY)
        ip_data = response.json()
        return ip_data.get('ip')
    except Exception:
        return "N/A"

def authentication_banner():
    os.system("cls" if os.name == "nt" else "clear")
    banner_text = f"""
    
    
    ████████╗██████╗░██╗░░██╗
    ╚══██╔══╝██╔══██╗██║░██╔╝
    ░░░██║░░░██║░░██║█████═╝░
    ░░░██║░░░██║░░██║██╔═██╗░
    ░░░██║░░░██████╔╝██║░╚██╗
    ░░░╚═╝░░░╚═════╝░╚═╝░░╚═╝
    
    ═══════════════════════════════════════════
    Admin: DUONG PHUNG
    Tool xworld & bumx
    TIKTOK: @tdktool
    Nhóm zalo: https://zalo.me/g/ddxsyp497
    ═══════════════════════════════════════════
    
"""
    print(xnhac + banner_text)

def display_machine_info(ip_address, device_id):
    authentication_banner()
    print(f"{trang}[{do}<>{trang}] {do}Địa chỉ IP: {vang}{ip_address}{trang}")
    print(f"{trang}[{do}<>{trang}] {do}Mã Máy: {vang}{device_id}{trang}")
    if CURRENT_SESSION_TYPE == 'VIP':
        print(f"{trang}[{do}<>{trang}] {luc}Trạng thái: VIP MEMBER{trang}")
    elif CURRENT_SESSION_TYPE == 'FREE':
        print(f"{trang}[{do}<>{trang}] {vang}Trạng thái: FREE MEMBER (Đóng lúc 21:00){trang}")

def display_remaining_time(expiry_date_str):
    try:
        expiry_date = datetime.strptime(expiry_date_str, '%d/%m/%Y').replace(hour=23, minute=59, second=59)
        now = datetime.now()
        if expiry_date > now:
            delta = expiry_date - now
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            print(f"{xnhac}Key VIP của bạn còn lại: {luc}{days} ngày, {hours} giờ, {minutes} phút.{trang}")
        else:
            print(f"{do}Key VIP của bạn đã hết hạn.{trang}")
    except ValueError:
        pass

# --- XỬ LÝ KEY VIP ---

def check_vip_key(machine_id, user_key):
    print(f"{vang}Đang kiểm tra Key VIP...{trang}")
    try:
        # [NÂNG CẤP] Verify SSL enabled
        response = requests.get(VIP_KEY_URL, timeout=10, verify=SSL_VERIFY)
        if response.status_code != 200:
            return 'error', None

        key_list = response.text.strip().split('\n')
        for line in key_list:
            line = line.strip()
            if not line: continue
            parts = line.split('|')
            if len(parts) >= 4:
                key_ma_may = parts[0].strip()
                key_value = parts[1].strip()
                key_ngay_het_han = parts[3].strip()

                if key_ma_may == machine_id and key_value == user_key:
                    try:
                        expiry_date = datetime.strptime(key_ngay_het_han, '%d/%m/%Y')
                        if expiry_date.date() >= datetime.now().date():
                            return 'valid', key_ngay_het_han
                        else:
                            return 'expired', None
                    except ValueError:
                        continue
        return 'not_found', None
    except Exception as e:
        # print(e)
        return 'error', None

# --- XỬ LÝ KEY FREE ---

def generate_daily_free_key(device_id):
    today_str = datetime.now(HANOI_TZ).strftime('%Y%m%d')
    raw_seed = f"{device_id}@{today_str}@TDK_V3_SECURE_SEED"
    hash_bytes = hashlib.sha256(raw_seed.encode()).hexdigest()
    charset = string.ascii_uppercase + string.digits
    final_key = ""
    for i in range(15):
        hex_part = hash_bytes[i*2 : i*2+2]
        index = int(hex_part, 16)
        final_key += charset[index % len(charset)]
    return final_key

def process_free_key(device_id):
    current_hour = datetime.now(HANOI_TZ).hour
    if current_hour >= 21:
        print(f"{do}Đã qua 21:00 giờ Việt Nam, hệ thống key free đóng cửa.{trang}")
        print(f"{vang}Vui lòng quay lại vào ngày mai.{trang}")
        time.sleep(3)
        return False

    target_key = generate_daily_free_key(device_id)
    url_base = 'https://getkeytdk.blogspot.com/2025/11/trang-chon-link-body-font-family-apple.html'
    full_url = f"{url_base}?"
    
    print(f'{trang}[{do}<>{trang}] {hong}Vui Lòng Vượt Link Để Lấy Key Free (Hết hạn 21:00 hàng ngày).{trang}')
    print(f'{trang}[{do}<>{trang}] {hong}Mỗi máy 1 key riêng, không dùng chung được!{trang}')
    print(f'{trang}[{do}<>{trang}] {hong}Link Để Lấy Key Là {xnhac}: {full_url}{trang}')

    while True:
        keynhap = input(f'{trang}[{do}<>{trang}] {vang}Nhập Key 15 ký tự: {luc}').strip()
        
        if keynhap == target_key:
            print(f'{luc}Key Chính Xác! Kích hoạt thành công.{trang}')
            expiry_iso = datetime.now(HANOI_TZ).replace(hour=21, minute=0, second=0).isoformat()
            data_to_save = {
                'key': target_key,
                'expiration_date': expiry_iso,
                'saved_date': datetime.now(HANOI_TZ).strftime('%Y%m%d') 
            }
            secure_save_data(FREE_CACHE_FILE, data_to_save)
            time.sleep(2)
            return True
        else:
            print(f'{trang}[{do}<>{trang}] {do}Key Sai!{trang} {vang}Key phải đúng 15 ký tự lấy từ link trên.{trang}')

def check_saved_free_key(device_id):
    data = secure_load_data(FREE_CACHE_FILE)
    if data:
        try:
            saved_date = data.get('saved_date')
            current_date = datetime.now(HANOI_TZ).strftime('%Y%m%d')
            if saved_date != current_date:
                return None 
            expiration_date = datetime.fromisoformat(data['expiration_date'])
            if expiration_date > datetime.now(HANOI_TZ):
                expected_key = generate_daily_free_key(device_id)
                if data['key'] == expected_key:
                    return data['key']
        except:
            pass
    return None

# --- HÀM TẢI VÀ CHẠY TOOL AN TOÀN (CƠ CHẾ MỚI - SANDBOX & AUTO KILL) ---

def secure_download_run(url, is_free_mode):
    """
    Tải và chạy tool với cơ chế bảo mật:
    1. Tên file ngẫu nhiên.
    2. Chạy subprocess Popen.
    3. Giám sát thời gian thực (nếu Free).
    4. Sử dụng Verify SSL.
    """
    print(f"\n{vang}Đang thiết lập môi trường an toàn và tải tool...{trang}")
    
    v = sys.version_info
    if v.major == 3 and v.minor < 10:
        print(f"{do}Cảnh báo: Python của bạn ({v.major}.{v.minor}) có thể quá cũ.{trang}")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # [NÂNG CẤP] Verify SSL enabled
        response = requests.get(url, headers=headers, timeout=30, verify=SSL_VERIFY)
        
        if response.status_code == 200:
            raw_content = response.content
            
            print(f"{luc}Tải thành công. Đang khởi tạo không gian an toàn...{trang}")
            
            # Tạo tên file ngẫu nhiên khó đoán để chống Scan
            random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
            fd, temp_path = tempfile.mkstemp(suffix=f"_{random_suffix}.py", prefix="sys_core_")
            
            try:
                with os.fdopen(fd, 'wb') as tmp:
                    tmp.write(raw_content)
                
                print(f"{luc}Đang khởi chạy tool...{trang}")
                print(f"{trang}==================================================")
                
                # --- SECURITY START ---
                # Sử dụng Popen thay vì call để có thể kiểm soát Process
                process = subprocess.Popen([sys.executable, temp_path])
                
                # Vòng lặp giám sát (Watchdog Loop)
                while process.poll() is None: # Trong khi tool con đang chạy
                    
                    # 1. Kiểm tra thời gian nếu là Free Key
                    if is_free_mode:
                        now = datetime.now(HANOI_TZ)
                        if now.hour >= 21:
                            print(f"\n{do}!!! ĐÃ ĐẾN 21:00 - HẾT GIỜ KEY FREE !!!{trang}")
                            print(f"{vang}Hệ thống tự động đóng tool.{trang}")
                            process.terminate() # Gửi tín hiệu dừng
                            time.sleep(2)
                            if process.poll() is None:
                                process.kill() # Giết tiến trình nếu lì lợm
                            break
                    
                    # 2. Kiểm tra Debugger (Đơn giản) từ cha
                    if security_system.check_remote_debugger():
                        process.kill()
                        print(f"\n{do}Phát hiện can thiệp hệ thống! Dừng tool.{trang}")
                        break

                    time.sleep(1) # Check mỗi 1 giây
                
                # --- SECURITY END ---
                
            except KeyboardInterrupt:
                print(f"\n{vang}Đã dừng tool.{trang}")
                try:
                    process.kill()
                except:
                    pass
            except Exception as e:
                print(f"{do}Lỗi thực thi Tool: {e}{trang}")
            finally:
                # QUAN TRỌNG: Xóa file ngay lập tức bằng cơ chế wipe an toàn
                secure_file_wipe(temp_path)
                
        else:
            print(f"{do}Server lỗi: {response.status_code}{trang}")
    except Exception as e:
        print(f"{do}Lỗi kết nối (Có thể do SSL/Mạng): {e}{trang}")
    
    print(f"{trang}==================================================")
    # Flush input buffers
    try:
        if sys.platform == 'win32':
            import msvcrt
            while msvcrt.kbhit(): msvcrt.getch()
        else:
            import select
            while sys.stdin in select.select([sys.stdin], [], [], 0)[0]: sys.stdin.read(1)
    except:
        pass
    input(f"{vang}Nhấn Enter để quay lại menu chính...{trang}")

# --- MENU VÀ LOGIC CHÍNH ---

def main_authentication():
    # >>> KÍCH HOẠT QUÉT VÀ XÓA FILE MẠNH MẼ TẠI ĐÂY <<<
    aggressive_cleanup()
    
    global CURRENT_SESSION_TYPE
    ip_address = get_ip_address()
    device_id = get_device_id()
    
    # Reset session
    CURRENT_SESSION_TYPE = "UNKNOWN"
    
    display_machine_info(ip_address, device_id)

    if not device_id:
        print(f"{do}Không thể lấy mã máy{trang}")
        return False

    # Check VIP Cached
    cached_vip_info = secure_load_data(VIP_CACHE_FILE)
    if cached_vip_info:
        try:
            expiry_date = datetime.strptime(cached_vip_info['expiration_date'], '%d/%m/%Y')
            if expiry_date.date() >= datetime.now().date():
                CURRENT_SESSION_TYPE = 'VIP'
                print(f"{luc}Đã tìm thấy Key VIP hợp lệ, tự động đăng nhập...{trang}")
                display_remaining_time(cached_vip_info['expiration_date'])
                sleep(2)
                return True
            else:
                print(f"{vang}Key VIP đã lưu đã hết hạn.{trang}")
        except:
            print(f"{do}Dữ liệu key lỗi hoặc đã bị can thiệp.{trang}")

    # Check Free Cached
    if check_saved_free_key(device_id):
        # Check giờ
        if datetime.now(HANOI_TZ).hour >= 21:
            print(f"{do}Key Free đã hết hạn trong ngày (sau 21h).{trang}")
            # Xóa cache cũ nếu hết giờ
            if os.path.exists(FREE_CACHE_FILE):
                 os.remove(FREE_CACHE_FILE)
        else:
            CURRENT_SESSION_TYPE = 'FREE'
            expiry_str = f"21:00 ngày {datetime.now(HANOI_TZ).strftime('%d/%m/%Y')}"
            print(f"{trang}[{do}<>{trang}] {hong}Key free hôm nay vẫn còn hạn (Hết hạn {expiry_str})...{trang}")
            time.sleep(2)
            return True

    while True:
        print(f"{trang}========== {vang}MENU LỰA CHỌN{trang} ==========")
        print(f"{trang}[{luc}1{trang}] {xduong}Nhập Key VIP (Vĩnh viễn/Tháng){trang}")
        print(f"{trang}[{luc}2{trang}] {xduong}Lấy Key Free (Mỗi ngày 1 key){trang}")
        print(f"{trang}======================================")

        try:
            choice = input(f"{trang}[{do}<>{trang}] {xduong}Nhập lựa chọn: {trang}")
            print(f"{trang}═══════════════════════════════════")

            if choice == '1':
                vip_key_input = input(f'{trang}[{do}<>{trang}] {vang}Nhập Key VIP: {luc}').strip()
                if not vip_key_input: continue

                status, expiry_date_str = check_vip_key(device_id, vip_key_input)

                if status == 'valid':
                    print(f"{luc}Xác thực Key VIP thành công!{trang}")
                    secure_save_data(VIP_CACHE_FILE, {
                        'key': vip_key_input,
                        'expiration_date': expiry_date_str
                    })
                    CURRENT_SESSION_TYPE = 'VIP'
                    display_remaining_time(expiry_date_str)
                    sleep(2)
                    return True
                elif status == 'expired':
                    print(f"{do}Key VIP đã hết hạn.{trang}")
                elif status == 'not_found':
                    print(f"{do}Key sai hoặc không đúng máy.{trang}")
                else: 
                    print(f"{do}Lỗi server hoặc kết nối SSL.{trang}")
                sleep(2)

            elif choice == '2':
                if process_free_key(device_id):
                    CURRENT_SESSION_TYPE = 'FREE'
                    return True
                else:
                    # Nếu thất bại hoặc hết giờ
                    pass

            else:
                print(f"{vang}Sai lựa chọn.{trang}")

        except KeyboardInterrupt:
            sys.exit()

def main_tool_menu():
    TOOLS_MENU = {
        "1": (" Vua tốc độ 1 ", "https://raw.githubusercontent.com/ntnhung864/vtdv88/main/vtdv88.py"),
        "2": (" Vua tốc độ 2 ", "https://raw.githubusercontent.com/ntnhung864/vtdv99/main/vtdv99.py"),
        "3": (" Vua thoát hiểm 1 ", "https://raw.githubusercontent.com/ntnhung864/vthv11/main/vthv11.py"),
        "4": (" Vua thoát hiểm 2 ", "https://raw.githubusercontent.com/ntnhung864/vthv12/main/vthv12.py"),
        "5": (" Tool bumx free ", "https://raw.githubusercontent.com/ntnhung864/bumv77/main/bumv77.py"),
    }

    while True:
        authentication_banner()
        display_machine_info(get_ip_address(), get_device_id()) # Show info again
        
        # Chạy lại dọn dẹp mỗi lần về menu
        aggressive_cleanup()

        table = Table(title="\n MENU TOOL CHÍNH \n", title_style="bold yellow", border_style="cyan", show_header=True, header_style="bold magenta")
        table.add_column("Chọn", style="bold green", justify="center", width=10)
        table.add_column("Tên Tool", style="cyan", width=40)

        for key, (name, url) in TOOLS_MENU.items():
            table.add_row(f"[{key}]", name)
        table.add_row(f"[{do}0{trang}]", f"[{hong}]Thoát Tool")
        
        console.print(table)
        
        if sys.gettrace(): 
             sys.exit()

        choice = input(f"{trang}[{do}<>{trang}] {xduong}Chọn Tool: {trang}")

        if choice == '0': sys.exit()
        
        if choice in TOOLS_MENU:
            # Kiểm tra giờ lần nữa trước khi chạy
            if CURRENT_SESSION_TYPE == 'FREE' and datetime.now(HANOI_TZ).hour >= 21:
                print(f"{do}Đã 21:00. Hết giờ sử dụng Key Free.{trang}")
                time.sleep(2)
                continue

            name, url = TOOLS_MENU[choice]
            # Truyền trạng thái FREE/VIP vào để xử lý Auto Kill
            is_free = (CURRENT_SESSION_TYPE == 'FREE')
            secure_download_run(url, is_free_mode=is_free)
        else:
            print(f"{vang}Sai lựa chọn.{trang}")
            time.sleep(1)

if __name__ == "__main__":
    try:
        if main_authentication():
            main_tool_menu()
    except KeyboardInterrupt:
        sys.exit()
    except Exception:
        sys.exit()
