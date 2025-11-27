"""
Test xuất báo cáo CSV
"""
import requests

SERVER = "http://192.168.1.184:8000"

def test_export_revenue():
    """Test xuất báo cáo doanh thu"""
    print("\n" + "="*60)
    print("📊 TEST XUẤT BÁO CÁO DOANH THU")
    print("="*60)
    
    # Test các tùy chọn khác nhau
    tests = [
        ("Hôm nay", "/api/export/revenue/?period=day&status=all"),
        ("Tuần này", "/api/export/revenue/?period=week&status=all"),
        ("Tháng này", "/api/export/revenue/?period=month&status=all"),
        ("Chỉ đã thanh toán", "/api/export/revenue/?period=month&status=paid"),
        ("Chỉ chưa thanh toán", "/api/export/revenue/?period=month&status=unpaid"),
    ]
    
    for name, url in tests:
        print(f"\n🔍 Test: {name}")
        print(f"   URL: {SERVER}{url}")
        
        try:
            response = requests.get(f"{SERVER}{url}", timeout=10)
            
            if response.status_code == 200:
                # Check if it's CSV
                if 'text/csv' in response.headers.get('Content-Type', ''):
                    lines = response.text.split('\n')
                    print(f"   ✅ Thành công! File CSV có {len(lines)} dòng")
                    print(f"   📄 Header: {lines[1] if len(lines) > 1 else 'N/A'}")
                    
                    # Save to file
                    filename = f"test_{name.replace(' ', '_').lower()}.csv"
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    print(f"   💾 Đã lưu: {filename}")
                else:
                    print(f"   ⚠️ Không phải CSV: {response.headers.get('Content-Type')}")
            else:
                print(f"   ❌ Error: HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}")
        
        except Exception as e:
            print(f"   ❌ Exception: {e}")

def test_export_detections():
    """Test xuất báo cáo phát hiện"""
    print("\n" + "="*60)
    print("🎥 TEST XUẤT BÁO CÁO PHÁT HIỆN")
    print("="*60)
    
    tests = [
        ("7 ngày - Tất cả", "/api/export/detections/?days=7&event_type=all"),
        ("7 ngày - Chỉ ENTRY", "/api/export/detections/?days=7&event_type=ENTRY"),
        ("7 ngày - Chỉ EXIT", "/api/export/detections/?days=7&event_type=EXIT"),
    ]
    
    for name, url in tests:
        print(f"\n🔍 Test: {name}")
        print(f"   URL: {SERVER}{url}")
        
        try:
            response = requests.get(f"{SERVER}{url}", timeout=10)
            
            if response.status_code == 200:
                if 'text/csv' in response.headers.get('Content-Type', ''):
                    lines = response.text.split('\n')
                    print(f"   ✅ Thành công! File CSV có {len(lines)} dòng")
                    
                    filename = f"test_detection_{name.replace(' ', '_').replace('-', '').lower()}.csv"
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    print(f"   💾 Đã lưu: {filename}")
                else:
                    print(f"   ⚠️ Không phải CSV")
            else:
                print(f"   ❌ Error: HTTP {response.status_code}")
        
        except Exception as e:
            print(f"   ❌ Exception: {e}")

def main():
    print("\n" + "="*60)
    print("🧪 TEST CHỨC NĂNG XUẤT BÁO CÁO CSV")
    print("="*60)
    print(f"\n📡 Server: {SERVER}")
    
    print("\n💡 Đảm bảo:")
    print("   1. Django server đang chạy")
    print("   2. Đã có dữ liệu trong database")
    print("   3. User đã login (hoặc bỏ @login_required)")
    
    input("\n✅ Nhấn Enter để bắt đầu test...")
    
    test_export_revenue()
    test_export_detections()
    
    print("\n" + "="*60)
    print("✅ TEST HOÀN THÀNH!")
    print("="*60)
    print("\n📁 Các file CSV đã được tạo trong thư mục hiện tại")
    print("💡 Mở file bằng Excel hoặc Google Sheets để xem")

if __name__ == '__main__':
    main()
