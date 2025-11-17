"""
Script test các API của hệ thống quản lý bãi đỗ xe
Chạy: python test_parking_api.py
"""

import requests
import json
from datetime import datetime, timedelta

# Cấu hình
BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api"

def print_response(title, response):
    """In response đẹp"""
    print(f"\n{'='*60}")
    print(f"📋 {title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except:
        print(response.text)

def test_revenue_statistics():
    """Test API thống kê doanh thu"""
    print("\n🔹 TEST 1: Thống kê doanh thu hôm nay")
    response = requests.get(f"{API_URL}/revenue/stats/", params={
        'period': 'day'
    })
    print_response("Thống kê ngày", response)
    
    print("\n🔹 TEST 2: Thống kê doanh thu tuần này")
    response = requests.get(f"{API_URL}/revenue/stats/", params={
        'period': 'week'
    })
    print_response("Thống kê tuần", response)
    
    print("\n🔹 TEST 3: Thống kê doanh thu tháng này")
    response = requests.get(f"{API_URL}/revenue/stats/", params={
        'period': 'month'
    })
    print_response("Thống kê tháng", response)

def test_revenue_charts():
    """Test API dữ liệu biểu đồ"""
    print("\n🔹 TEST 4: Doanh thu 7 ngày gần nhất")
    response = requests.get(f"{API_URL}/revenue/daily/", params={
        'days': 7
    })
    print_response("Biểu đồ 7 ngày", response)
    
    print("\n🔹 TEST 5: Doanh thu 12 tháng năm 2025")
    response = requests.get(f"{API_URL}/revenue/monthly/", params={
        'year': 2025
    })
    print_response("Biểu đồ 12 tháng", response)

def test_active_sessions():
    """Test API danh sách xe đang đỗ"""
    print("\n🔹 TEST 6: Danh sách xe đang đỗ")
    response = requests.get(f"{API_URL}/sessions/active/")
    print_response("Xe đang đỗ", response)

def test_session_detail():
    """Test API chi tiết giao dịch"""
    print("\n🔹 TEST 7: Chi tiết giao dịch")
    
    # Lấy session đầu tiên
    response = requests.get(f"{API_URL}/sessions/history/", params={'limit': 1})
    data = response.json()
    
    if data['sessions']:
        session_id = data['sessions'][0]['id']
        response = requests.get(f"{API_URL}/sessions/{session_id}/")
        print_response(f"Chi tiết giao dịch #{session_id}", response)
    else:
        print("⚠️ Chưa có giao dịch nào trong hệ thống")

def test_unpaid_sessions():
    """Test API danh sách chưa thanh toán"""
    print("\n🔹 TEST 8: Danh sách chưa thanh toán")
    response = requests.get(f"{API_URL}/sessions/unpaid/")
    print_response("Chưa thanh toán", response)

def test_payment():
    """Test API thanh toán"""
    print("\n🔹 TEST 9: Thanh toán giao dịch")
    
    # Lấy session chưa thanh toán đầu tiên
    response = requests.get(f"{API_URL}/sessions/unpaid/")
    data = response.json()
    
    if data['sessions']:
        session_id = data['sessions'][0]['id']
        print(f"Đang thanh toán giao dịch #{session_id}...")
        
        response = requests.post(f"{API_URL}/sessions/{session_id}/pay/")
        print_response(f"Thanh toán #{session_id}", response)
    else:
        print("⚠️ Không có giao dịch nào cần thanh toán")

def test_transaction_history():
    """Test API lịch sử giao dịch"""
    print("\n🔹 TEST 10: Lịch sử giao dịch (phân trang)")
    response = requests.get(f"{API_URL}/sessions/history/", params={
        'page': 1,
        'limit': 5
    })
    print_response("Lịch sử (trang 1)", response)
    
    print("\n🔹 TEST 11: Lịch sử theo biển số")
    response = requests.get(f"{API_URL}/sessions/history/", params={
        'license_plate': '30A',
        'limit': 5
    })
    print_response("Lọc theo biển số '30A'", response)
    
    print("\n🔹 TEST 12: Lịch sử đã thanh toán")
    response = requests.get(f"{API_URL}/sessions/history/", params={
        'payment_status': 'PAID',
        'limit': 5
    })
    print_response("Lọc đã thanh toán", response)

def test_fee_calculation():
    """Test tính phí (không cần API, test trực tiếp)"""
    print("\n🔹 TEST 13: Tính phí các trường hợp")
    print("="*60)
    
    test_cases = [
        (20, 0, "20 phút - Miễn phí"),
        (30, 0, "30 phút - Miễn phí"),
        (45, 5000, "45 phút - Giờ đầu"),
        (90, 5000, "1h 30p - Giờ đầu"),
        (105, 8000, "1h 45p - Có 1 giờ thêm"),
        (150, 8000, "2h 30p - Có 1 giờ thêm"),
        (165, 11000, "2h 45p - Có 2 giờ thêm"),
        (255, 14000, "4h 15p - Có 3 giờ thêm"),
    ]
    
    for duration, expected, description in test_cases:
        # Giả lập logic tính phí
        import math
        if duration <= 30:
            fee = 0
        elif duration <= 90:
            fee = 5000
        else:
            remaining = duration - 90
            additional_hours = math.ceil(remaining / 60)
            fee = 5000 + (additional_hours * 3000)
        
        status = "✅" if fee == expected else "❌"
        print(f"{status} {description}: {fee:,}đ (Kỳ vọng: {expected:,}đ)")

def simulate_vehicle_entry_exit():
    """Mô phỏng xe vào và ra"""
    print("\n🔹 TEST 14: Mô phỏng xe vào/ra")
    print("="*60)
    
    # Giả lập POST từ Raspberry Pi
    license_plate = "30A99999"
    
    print(f"\n1️⃣ Xe {license_plate} VÀO bãi...")
    response = requests.post(f"{API_URL}/upload/", data={
        'license_plate': license_plate,
        'confidence': 0.95,
        'camera_source': 'test_camera'
    })
    print_response("ENTRY event", response)
    
    print(f"\n⏳ Đợi 2 giây (giả lập xe đỗ)...")
    import time
    time.sleep(2)
    
    print(f"\n2️⃣ Xe {license_plate} RA khỏi bãi...")
    response = requests.post(f"{API_URL}/upload/", data={
        'license_plate': license_plate,
        'confidence': 0.96,
        'camera_source': 'test_camera'
    })
    print_response("EXIT event", response)

def main():
    """Chạy tất cả tests"""
    print("\n" + "="*60)
    print("🚗 BẮT ĐẦU TEST HỆ THỐNG QUẢN LÝ BÃI ĐỖ XE")
    print("="*60)
    
    try:
        # Test thống kê
        test_revenue_statistics()
        test_revenue_charts()
        
        # Test quản lý giao dịch
        test_active_sessions()
        test_session_detail()
        test_unpaid_sessions()
        test_transaction_history()
        
        # Test thanh toán (có thể thay đổi dữ liệu)
        # test_payment()  # Bỏ comment nếu muốn test
        
        # Test logic
        test_fee_calculation()
        
        # Test mô phỏng (tạo dữ liệu mới)
        # simulate_vehicle_entry_exit()  # Bỏ comment nếu muốn test
        
        print("\n" + "="*60)
        print("✅ HOÀN THÀNH TẤT CẢ TESTS")
        print("="*60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ LỖI: Không kết nối được đến server")
        print("Đảm bảo Django server đang chạy: python manage.py runserver")
    except Exception as e:
        print(f"\n❌ LỖI: {str(e)}")

if __name__ == "__main__":
    main()
