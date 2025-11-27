"""
Script test đơn giản - không cần sensor
Giả lập EXIT để test payment modal
"""

import requests
import json

SERVER = "http://192.168.1.184:8000"

def list_active_sessions():
    """Liệt kê các xe đang đỗ (ACTIVE)"""
    print("\n" + "="*60)
    print("🚗 XE ĐANG ĐỖ (ACTIVE SESSIONS)")
    print("="*60)
    
    try:
        response = requests.get(f"{SERVER}/api/sessions/active/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            sessions = data.get('sessions', [])
            
            if sessions:
                print(f"\n✅ Có {len(sessions)} xe đang đỗ:\n")
                for i, s in enumerate(sessions, 1):
                    print(f"{i}. 🎫 {s['license_plate']}")
                    print(f"   ⏰ Vào lúc: {s['entry_time']}")
                    print(f"   🆔 Session ID: {s['id']}\n")
                return sessions
            else:
                print("\n⚠️ Không có xe nào đang đỗ")
                print("💡 Chạy: python manage.py generate_parking_data --sessions 20")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return []

def list_unpaid_sessions():
    """Liệt kê các phiên chưa thanh toán"""
    print("\n" + "="*60)
    print("💰 PHIÊN CHƯA THANH TOÁN (UNPAID)")
    print("="*60)
    
    try:
        response = requests.get(f"{SERVER}/api/sessions/unpaid/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            sessions = data.get('sessions', [])
            
            if sessions:
                print(f"\n✅ Có {len(sessions)} phiên chưa thanh toán:\n")
                total_unpaid = 0
                for i, s in enumerate(sessions, 1):
                    print(f"{i}. 🎫 {s['license_plate']}")
                    print(f"   💵 Phí: {s['fee']:,}đ")
                    print(f"   ⏱️ Thời gian: {s['duration_minutes']} phút")
                    print(f"   🆔 Session ID: {s['id']}\n")
                    total_unpaid += s['fee']
                
                print(f"📊 Tổng công nợ: {total_unpaid:,}đ")
                return sessions
            else:
                print("\n✅ Không có phiên nào chưa thanh toán")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return []

def simulate_exit_manual(session_id):
    """
    Giả lập EXIT thủ công bằng cách complete session
    """
    print(f"\n{'='*60}")
    print(f"🚪 GIẢI LẬP XE RA (EXIT) - Session #{session_id}")
    print("="*60)
    
    # Get session detail
    try:
        response = requests.get(f"{SERVER}/api/sessions/{session_id}/", timeout=5)
        if response.status_code == 200:
            session = response.json().get('session')
            if not session:
                print("❌ Session không tồn tại")
                return
            
            plate = session['license_plate']
            status = session['status']
            
            print(f"\n📋 Thông tin session:")
            print(f"   Biển số: {plate}")
            print(f"   Trạng thái: {status}")
            print(f"   Vào lúc: {session['entry_time']}")
            
            if status != 'ACTIVE':
                print(f"\n⚠️ Session đã kết thúc (status={status})")
                return
            
            # Để complete session, ta cần gọi API hoặc trực tiếp trong Django
            print(f"\n💡 Để test EXIT cho session này:")
            print(f"   1. Vào Django shell: python manage.py shell")
            print(f"   2. Chạy code:")
            print(f"""
from parking.models import ParkingSession
from django.utils import timezone

session = ParkingSession.objects.get(id={session_id})
session.complete_session(timezone.now())
print(f"✅ EXIT: {{session.license_plate}} - Fee: {{session.fee:,}}đ")
            """)
            
            print(f"\n   3. Hoặc dùng API upload với plate: {plate}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def check_latest_detection():
    """Kiểm tra detection mới nhất"""
    print("\n" + "="*60)
    print("🔍 DETECTION MỚI NHẤT")
    print("="*60)
    
    try:
        response = requests.get(f"{SERVER}/api/latest_detections/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            latest = data.get('latest')
            
            if latest:
                print(f"\n✅ Detection mới nhất:")
                print(f"   Biển số: {latest.get('plate')}")
                print(f"   Thời gian: {latest.get('time')}")
                print(f"   Event: {latest.get('event', 'N/A')}")
                print(f"   Confidence: {latest.get('conf')}")
                
                if latest.get('event') == 'EXIT':
                    print(f"\n🎯 Đây là EXIT event - payment modal nên xuất hiện!")
            else:
                print("\n⚠️ Chưa có detection nào")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

def main_menu():
    """Menu chính"""
    while True:
        print("\n" + "="*60)
        print("🧪 TEST PAYMENT ON EXIT - MENU")
        print("="*60)
        print("\n1. 📋 Liệt kê xe đang đỗ (ACTIVE)")
        print("2. 💰 Liệt kê phiên chưa thanh toán (UNPAID)")
        print("3. 🔍 Kiểm tra detection mới nhất")
        print("4. 🚪 Giả lập EXIT cho session")
        print("5. 🌐 Mở dashboard trong browser")
        print("0. ❌ Thoát")
        
        choice = input("\n👉 Chọn (0-5): ").strip()
        
        if choice == '1':
            list_active_sessions()
        elif choice == '2':
            list_unpaid_sessions()
        elif choice == '3':
            check_latest_detection()
        elif choice == '4':
            sessions = list_active_sessions()
            if sessions:
                try:
                    idx = int(input(f"\n👉 Chọn session (1-{len(sessions)}): ")) - 1
                    if 0 <= idx < len(sessions):
                        simulate_exit_manual(sessions[idx]['id'])
                except ValueError:
                    print("❌ Vui lòng nhập số")
        elif choice == '5':
            import webbrowser
            url = f"{SERVER}/dashboard_user/"
            print(f"\n🌐 Mở browser: {url}")
            webbrowser.open(url)
        elif choice == '0':
            print("\n👋 Bye!")
            break
        else:
            print("\n❌ Lựa chọn không hợp lệ")
        
        input("\n⏸️  Nhấn Enter để tiếp tục...")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 SMART PARKING - PAYMENT TEST TOOL")
    print("="*60)
    print(f"\n📡 Server: {SERVER}")
    print("\n💡 Đảm bảo Django server đang chạy:")
    print("   python manage.py runserver 0.0.0.0:8000")
    
    input("\n✅ Nhấn Enter để bắt đầu...")
    
    main_menu()
