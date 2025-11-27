"""
Script test chức năng thanh toán khi nhận diện event EXIT
Giả lập Raspberry Pi gửi dữ liệu xe ra bãi
"""

import requests
import time
from pathlib import Path

# Cấu hình
DJANGO_SERVER = "http://192.168.1.184:8000"  # Hoặc localhost:8000
API_ENDPOINT = f"{DJANGO_SERVER}/api/upload/"

# Test với biển số xe có trong fake data
TEST_PLATES = [
    '29A12345',
    '30B67890', 
    '51C11111',
    '59D22222',
    '79E33333'
]

def create_test_image():
    """Tạo ảnh test đơn giản (hoặc dùng ảnh có sẵn)"""
    # Tạo file ảnh giả lập
    test_image_path = Path(__file__).parent / "test_plate.jpg"
    
    if not test_image_path.exists():
        # Tạo ảnh trắng đơn giản bằng PIL
        try:
            from PIL import Image
            img = Image.new('RGB', (640, 480), color='white')
            img.save(test_image_path)
            print(f"✅ Created test image: {test_image_path}")
        except ImportError:
            print("⚠️ PIL not installed, creating dummy file")
            with open(test_image_path, 'wb') as f:
                f.write(b'\xff\xd8\xff\xe0')  # JPEG header
    
    return test_image_path

def test_entry(plate, confidence=0.95):
    """
    Test event ENTRY - Xe vào bãi
    """
    print(f"\n{'='*60}")
    print(f"🚗 TEST ENTRY: {plate}")
    print(f"{'='*60}")
    
    test_image = create_test_image()
    
    # Chuẩn bị data
    data = {
        'plate': plate,
        'confidence': str(confidence),
        'source': 'test_camera'
    }
    
    # Chuẩn bị file
    with open(test_image, 'rb') as f:
        files = {'image': ('test_plate.jpg', f, 'image/jpeg')}
        
        try:
            response = requests.post(API_ENDPOINT, data=data, files=files, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Status: {result.get('status')}")
                print(f"📝 Event: {result.get('event_type')}")
                print(f"🎫 Plate: {result.get('plate')}")
                print(f"💯 Confidence: {result.get('confidence')}")
                print(f"📋 Message: {result.get('message')}")
                
                if 'session_id' in result:
                    print(f"🆔 Session ID: {result.get('session_id')}")
                    return result.get('session_id')
                
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
    
    return None

def test_exit(plate, confidence=0.93):
    """
    Test event EXIT - Xe ra bãi
    Sẽ tự động kích hoạt modal thanh toán trên dashboard
    """
    print(f"\n{'='*60}")
    print(f"🚗 TEST EXIT: {plate}")
    print(f"{'='*60}")
    
    test_image = create_test_image()
    
    # Chuẩn bị data
    data = {
        'plate': plate,
        'confidence': str(confidence),
        'source': 'test_camera'
    }
    
    # Chuẩn bị file
    with open(test_image, 'rb') as f:
        files = {'image': ('test_plate.jpg', f, 'image/jpeg')}
        
        try:
            response = requests.post(API_ENDPOINT, data=data, files=files, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Status: {result.get('status')}")
                print(f"📝 Event: {result.get('event_type')}")
                print(f"🎫 Plate: {result.get('plate')}")
                print(f"💯 Confidence: {result.get('confidence')}")
                print(f"📋 Message: {result.get('message')}")
                
                if result.get('event_type') == 'EXIT':
                    print(f"\n💰 PAYMENT DETAILS:")
                    print(f"   Session ID: {result.get('session_id')}")
                    print(f"   Duration: {result.get('duration_minutes')} minutes")
                    print(f"   Fee: {result.get('fee'):,}đ")
                    print(f"   Payment Status: {result.get('payment_status')}")
                    print(f"   Display: {result.get('display_message')}")
                    
                    if 'fee_breakdown' in result:
                        breakdown = result['fee_breakdown']
                        print(f"\n📊 FEE BREAKDOWN:")
                        print(f"   First 90 min: {breakdown.get('first_period_fee'):,}đ")
                        if breakdown.get('additional_hours', 0) > 0:
                            print(f"   Additional {breakdown.get('additional_hours')}h: {breakdown.get('additional_fee'):,}đ")
                    
                    print(f"\n🎯 NEXT STEP:")
                    print(f"   → Dashboard sẽ tự động hiển thị payment modal")
                    print(f"   → Kiểm tra dashboard_user để xác nhận modal xuất hiện")
                    
                return result
                
            else:
                print(f"❌ HTTP Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
    
    return None

def check_unpaid_sessions():
    """
    Kiểm tra các phiên chưa thanh toán
    """
    print(f"\n{'='*60}")
    print(f"📋 CHECKING UNPAID SESSIONS")
    print(f"{'='*60}")
    
    try:
        response = requests.get(f"{DJANGO_SERVER}/api/sessions/unpaid/", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                sessions = data.get('sessions', [])
                print(f"✅ Found {len(sessions)} unpaid sessions:")
                
                for session in sessions:
                    print(f"\n   🎫 {session['license_plate']}")
                    print(f"      Fee: {session['fee']:,}đ")
                    print(f"      Duration: {session['duration_minutes']} min")
                    print(f"      Entry: {session['entry_time']}")
                    print(f"      Exit: {session['exit_time']}")
                
                return sessions
            else:
                print(f"❌ API returned error")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    
    return []

def run_full_test():
    """
    Chạy test đầy đủ: ENTRY -> EXIT -> Check Payment
    """
    print("\n" + "="*60)
    print("🚀 STARTING FULL PAYMENT TEST")
    print("="*60)
    
    test_plate = TEST_PLATES[0]  # Sử dụng biển số đầu tiên
    
    # Step 1: Test ENTRY
    print(f"\n📍 STEP 1: Simulate vehicle ENTRY")
    session_id = test_entry(test_plate)
    
    if not session_id:
        print("❌ ENTRY failed, cannot proceed to EXIT test")
        return
    
    print(f"\n⏳ Waiting 3 seconds before EXIT...")
    time.sleep(3)
    
    # Step 2: Test EXIT
    print(f"\n📍 STEP 2: Simulate vehicle EXIT")
    exit_result = test_exit(test_plate)
    
    if not exit_result:
        print("❌ EXIT failed")
        return
    
    print(f"\n⏳ Waiting 2 seconds before checking sessions...")
    time.sleep(2)
    
    # Step 3: Check unpaid sessions
    print(f"\n📍 STEP 3: Check unpaid sessions")
    unpaid = check_unpaid_sessions()
    
    # Summary
    print(f"\n" + "="*60)
    print("✅ TEST COMPLETED")
    print("="*60)
    print(f"\n📊 SUMMARY:")
    print(f"   Test Plate: {test_plate}")
    print(f"   Session ID: {session_id}")
    print(f"   Fee: {exit_result.get('fee', 0):,}đ")
    print(f"   Unpaid Sessions: {len(unpaid)}")
    
    print(f"\n🎯 MANUAL VERIFICATION:")
    print(f"   1. Mở dashboard: {DJANGO_SERVER}/dashboard_user/")
    print(f"   2. Login với tài khoản nhân viên")
    print(f"   3. Kiểm tra xem payment modal có tự động hiện không")
    print(f"   4. Modal nên hiển thị thông tin xe {test_plate}")
    print(f"   5. Click 'THANH TOÁN NGAY' để test payment API")

def test_with_existing_session():
    """
    Test EXIT với session đã tồn tại trong fake data
    """
    print("\n" + "="*60)
    print("🚀 TEST WITH EXISTING SESSION")
    print("="*60)
    
    # Kiểm tra unpaid sessions hiện có
    unpaid = check_unpaid_sessions()
    
    if not unpaid:
        print("\n⚠️ No existing unpaid sessions found")
        print("💡 Run: python manage.py generate_parking_data --sessions 20")
        return
    
    # Lấy session đầu tiên
    test_session = unpaid[0]
    test_plate = test_session['license_plate']
    
    print(f"\n🎯 Testing EXIT for existing session: {test_plate}")
    print(f"   Current fee: {test_session['fee']:,}đ")
    
    # Giả lập EXIT
    exit_result = test_exit(test_plate)
    
    if exit_result:
        print(f"\n✅ EXIT test successful!")
        print(f"💡 Check dashboard to see if payment modal appears")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Test payment functionality on EXIT event')
    parser.add_argument('--mode', choices=['full', 'exit', 'check', 'existing'],
                      default='full',
                      help='Test mode: full (ENTRY+EXIT), exit (EXIT only), check (list unpaid), existing (use existing session)')
    parser.add_argument('--plate', type=str,
                      help='License plate to test (default: use first test plate)')
    
    args = parser.parse_args()
    
    if args.mode == 'full':
        run_full_test()
    elif args.mode == 'exit':
        plate = args.plate or TEST_PLATES[0]
        test_exit(plate)
    elif args.mode == 'check':
        check_unpaid_sessions()
    elif args.mode == 'existing':
        test_with_existing_session()
