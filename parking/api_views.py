"""
API Views cho hệ thống quản lý bãi đỗ xe
Bao gồm: Thống kê doanh thu, quản lý giao dịch, thanh toán
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Count, Q, Avg
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .models import ParkingSession, VehicleDetection


# ==================== API THỐNG KÊ DOANH THU ====================

@require_http_methods(["GET"])
def revenue_statistics(request):
    """
    API thống kê doanh thu tổng quát
    
    Query Parameters:
        - period: 'day', 'week', 'month', 'year' (mặc định: 'day')
        - date: 'YYYY-MM-DD' (mặc định: hôm nay)
    
    Returns:
        {
            "period": "day",
            "date": "2025-11-17",
            "total_revenue": 150000,
            "total_transactions": 25,
            "paid_transactions": 20,
            "unpaid_transactions": 3,
            "free_transactions": 2,
            "average_fee": 6000,
            "average_duration": 85
        }
    """
    period = request.GET.get('period', 'day')
    date_str = request.GET.get('date')
    
    # Xác định ngày cần thống kê
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Định dạng ngày không hợp lệ. Dùng YYYY-MM-DD'}, status=400)
    else:
        target_date = timezone.localtime().date()
    
    # Tính khoảng thời gian
    if period == 'day':
        start_time = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
        end_time = start_time + timedelta(days=1)
        period_label = target_date.strftime('%d/%m/%Y')
    
    elif period == 'week':
        # Tuần bắt đầu từ thứ 2
        start_time = timezone.make_aware(datetime.combine(target_date - timedelta(days=target_date.weekday()), datetime.min.time()))
        end_time = start_time + timedelta(days=7)
        period_label = f"Tuần {start_time.strftime('%d/%m')} - {end_time.strftime('%d/%m/%Y')}"
    
    elif period == 'month':
        start_time = timezone.make_aware(datetime(target_date.year, target_date.month, 1))
        if target_date.month == 12:
            end_time = timezone.make_aware(datetime(target_date.year + 1, 1, 1))
        else:
            end_time = timezone.make_aware(datetime(target_date.year, target_date.month + 1, 1))
        period_label = target_date.strftime('%m/%Y')
    
    elif period == 'year':
        start_time = timezone.make_aware(datetime(target_date.year, 1, 1))
        end_time = timezone.make_aware(datetime(target_date.year + 1, 1, 1))
        period_label = str(target_date.year)
    
    else:
        return JsonResponse({'error': 'Period không hợp lệ. Chọn: day, week, month, year'}, status=400)
    
    # Truy vấn dữ liệu
    sessions = ParkingSession.objects.filter(
        exit_time__gte=start_time,
        exit_time__lt=end_time,
        status='COMPLETED'
    )
    
    # Tính toán thống kê
    stats = sessions.aggregate(
        total_revenue=Sum('fee'),
        total_transactions=Count('id'),
        paid_count=Count('id', filter=Q(payment_status='PAID')),
        unpaid_count=Count('id', filter=Q(payment_status='UNPAID')),
        free_count=Count('id', filter=Q(payment_status='FREE')),
        avg_fee=Avg('fee'),
        avg_duration=Avg('duration_minutes')
    )
    
    return JsonResponse({
        'success': True,
        'period': period,
        'period_label': period_label,
        'date_range': {
            'start': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'end': end_time.strftime('%Y-%m-%d %H:%M:%S')
        },
        'total_revenue': int(stats['total_revenue'] or 0),
        'total_transactions': stats['total_transactions'],
        'paid_transactions': stats['paid_count'],
        'unpaid_transactions': stats['unpaid_count'],
        'free_transactions': stats['free_count'],
        'average_fee': int(stats['avg_fee'] or 0),
        'average_duration_minutes': int(stats['avg_duration'] or 0)
    })


@require_http_methods(["GET"])
def revenue_by_day(request):
    """
    API thống kê doanh thu theo từng ngày (dùng cho biểu đồ)
    
    Query Parameters:
        - days: số ngày lấy dữ liệu (mặc định: 7)
    
    Returns:
        {
            "labels": ["17/11", "18/11", ...],
            "revenue": [50000, 75000, ...],
            "transactions": [10, 15, ...]
        }
    """
    days = int(request.GET.get('days', 7))
    
    end_date = timezone.localtime().date()
    start_date = end_date - timedelta(days=days-1)
    
    # Truy vấn theo ngày
    daily_stats = ParkingSession.objects.filter(
        exit_time__date__gte=start_date,
        exit_time__date__lte=end_date,
        status='COMPLETED'
    ).annotate(
        date=TruncDate('exit_time')
    ).values('date').annotate(
        revenue=Sum('fee'),
        count=Count('id')
    ).order_by('date')
    
    # Tạo dict để đảm bảo có đủ các ngày (kể cả ngày 0 giao dịch)
    stats_dict = {stat['date']: stat for stat in daily_stats}
    
    labels = []
    revenue = []
    transactions = []
    
    current_date = start_date
    while current_date <= end_date:
        labels.append(current_date.strftime('%d/%m'))
        
        if current_date in stats_dict:
            revenue.append(int(stats_dict[current_date]['revenue'] or 0))
            transactions.append(stats_dict[current_date]['count'])
        else:
            revenue.append(0)
            transactions.append(0)
        
        current_date += timedelta(days=1)
    
    return JsonResponse({
        'success': True,
        'labels': labels,
        'revenue': revenue,
        'transactions': transactions
    })


@require_http_methods(["GET"])
def revenue_by_month(request):
    """
    API thống kê doanh thu theo từng tháng (dùng cho biểu đồ năm)
    
    Query Parameters:
        - year: năm cần thống kê (mặc định: năm hiện tại)
    
    Returns:
        {
            "labels": ["01/2025", "02/2025", ...],
            "revenue": [500000, 750000, ...],
            "transactions": [100, 150, ...]
        }
    """
    year = int(request.GET.get('year', timezone.localtime().year))
    
    # Truy vấn theo tháng
    monthly_stats = ParkingSession.objects.filter(
        exit_time__year=year,
        status='COMPLETED'
    ).annotate(
        month=TruncMonth('exit_time')
    ).values('month').annotate(
        revenue=Sum('fee'),
        count=Count('id')
    ).order_by('month')
    
    # Tạo dict
    stats_dict = {stat['month'].month: stat for stat in monthly_stats}
    
    labels = []
    revenue = []
    transactions = []
    
    for month in range(1, 13):
        labels.append(f"{month:02d}/{year}")
        
        if month in stats_dict:
            revenue.append(int(stats_dict[month]['revenue'] or 0))
            transactions.append(stats_dict[month]['count'])
        else:
            revenue.append(0)
            transactions.append(0)
    
    return JsonResponse({
        'success': True,
        'year': year,
        'labels': labels,
        'revenue': revenue,
        'transactions': transactions
    })


# ==================== API QUẢN LÝ GIAO DỊCH ====================

@require_http_methods(["GET"])
def get_active_sessions(request):
    """
    Lấy danh sách xe đang đỗ (ACTIVE)
    
    Returns:
        {
            "success": true,
            "count": 5,
            "sessions": [
                {
                    "id": 1,
                    "license_plate": "30A12345",
                    "entry_time": "2025-11-17 08:30:00",
                    "duration_minutes": 45,
                    "entry_image": "detections/entry_123.jpg"
                }
            ]
        }
    """
    sessions = ParkingSession.objects.filter(status='ACTIVE').order_by('-entry_time')
    
    data = []
    current_time = timezone.localtime()
    
    for session in sessions:
        # Tính thời gian đỗ hiện tại
        duration = current_time - timezone.localtime(session.entry_time)
        duration_minutes = int(duration.total_seconds() / 60)
        
        # Tính phí ước tính nếu xe ra ngay
        estimated_fee = session.calculate_fee(duration_minutes)
        
        data.append({
            'id': session.id,
            'license_plate': session.license_plate,
            'entry_time': timezone.localtime(session.entry_time).strftime('%Y-%m-%d %H:%M:%S'),
            'duration_minutes': duration_minutes,
            'estimated_fee': int(estimated_fee),
            'entry_image': session.entry_image or ''
        })
    
    return JsonResponse({
        'success': True,
        'count': len(data),
        'sessions': data
    })


@require_http_methods(["GET"])
def get_session_detail(request, session_id):
    """
    Lấy chi tiết 1 giao dịch
    
    Returns:
        {
            "success": true,
            "session": {
                "id": 1,
                "license_plate": "30A12345",
                "entry_time": "...",
                "exit_time": "...",
                "duration_minutes": 125,
                "fee": 8000,
                "fee_breakdown": {...},
                "payment_status": "UNPAID",
                "status": "COMPLETED"
            }
        }
    """
    try:
        session = ParkingSession.objects.get(id=session_id)
    except ParkingSession.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Giao dịch không tồn tại'}, status=404)
    
    data = {
        'id': session.id,
        'license_plate': session.license_plate,
        'entry_time': timezone.localtime(session.entry_time).strftime('%Y-%m-%d %H:%M:%S'),
        'exit_time': timezone.localtime(session.exit_time).strftime('%Y-%m-%d %H:%M:%S') if session.exit_time else None,
        'duration_minutes': session.duration_minutes,
        'fee': int(session.fee),
        'fee_breakdown': session.get_fee_breakdown(),
        'payment_status': session.payment_status,
        'payment_status_display': session.get_payment_status_display(),
        'status': session.status,
        'status_display': session.get_status_display(),
        'entry_image': session.entry_image or '',
        'exit_image': session.exit_image or ''
    }
    
    return JsonResponse({
        'success': True,
        'session': data
    })


@csrf_exempt
@require_http_methods(["POST"])
def mark_session_paid(request, session_id):
    """
    Đánh dấu giao dịch đã thanh toán
    
    POST /api/sessions/<id>/pay/
    Body: {} (không cần data)
    
    Returns:
        {
            "success": true,
            "message": "Đã thanh toán thành công",
            "session": {...}
        }
    """
    try:
        session = ParkingSession.objects.get(id=session_id)
    except ParkingSession.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Giao dịch không tồn tại'}, status=404)
    
    # Kiểm tra trạng thái
    if session.status != 'COMPLETED':
        return JsonResponse({'success': False, 'error': 'Chỉ thanh toán được giao dịch đã hoàn thành'}, status=400)
    
    if session.payment_status == 'PAID':
        return JsonResponse({'success': False, 'error': 'Giao dịch đã được thanh toán rồi'}, status=400)
    
    if session.payment_status == 'FREE':
        return JsonResponse({'success': False, 'error': 'Giao dịch miễn phí không cần thanh toán'}, status=400)
    
    # Thanh toán
    session.mark_as_paid()
    
    return JsonResponse({
        'success': True,
        'message': 'Đã thanh toán thành công',
        'session': {
            'id': session.id,
            'license_plate': session.license_plate,
            'fee': int(session.fee),
            'payment_status': session.payment_status
        }
    })


@require_http_methods(["GET"])
def get_unpaid_sessions(request):
    """
    Lấy danh sách giao dịch chưa thanh toán
    
    Returns:
        {
            "success": true,
            "count": 3,
            "total_debt": 25000,
            "sessions": [...]
        }
    """
    sessions = ParkingSession.objects.filter(
        status='COMPLETED',
        payment_status='UNPAID'
    ).order_by('-exit_time')
    
    data = []
    total_debt = 0
    
    for session in sessions:
        total_debt += session.fee
        data.append({
            'id': session.id,
            'license_plate': session.license_plate,
            'entry_time': timezone.localtime(session.entry_time).strftime('%Y-%m-%d %H:%M:%S'),
            'exit_time': timezone.localtime(session.exit_time).strftime('%Y-%m-%d %H:%M:%S'),
            'duration_minutes': session.duration_minutes,
            'fee': int(session.fee)
        })
    
    return JsonResponse({
        'success': True,
        'count': len(data),
        'total_debt': int(total_debt),
        'sessions': data
    })


# ==================== API LỊCH SỬ GIAO DỊCH ====================

@require_http_methods(["GET"])
def get_transaction_history(request):
    """
    Lấy lịch sử giao dịch với phân trang và filter
    
    Query Parameters:
        - page: trang (mặc định: 1)
        - limit: số item/trang (mặc định: 20)
        - license_plate: lọc theo biển số
        - payment_status: PAID, UNPAID, FREE
        - from_date: YYYY-MM-DD
        - to_date: YYYY-MM-DD
    
    Returns:
        {
            "success": true,
            "page": 1,
            "limit": 20,
            "total": 150,
            "sessions": [...]
        }
    """
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 20))
    
    # Base query
    queryset = ParkingSession.objects.filter(status='COMPLETED')
    
    # Filters
    license_plate = request.GET.get('license_plate')
    if license_plate:
        queryset = queryset.filter(license_plate__icontains=license_plate)
    
    payment_status = request.GET.get('payment_status')
    if payment_status:
        queryset = queryset.filter(payment_status=payment_status)
    
    from_date = request.GET.get('from_date')
    if from_date:
        try:
            from_dt = datetime.strptime(from_date, '%Y-%m-%d')
            queryset = queryset.filter(exit_time__gte=timezone.make_aware(from_dt))
        except ValueError:
            pass
    
    to_date = request.GET.get('to_date')
    if to_date:
        try:
            to_dt = datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)
            queryset = queryset.filter(exit_time__lt=timezone.make_aware(to_dt))
        except ValueError:
            pass
    
    # Count total
    total = queryset.count()
    
    # Pagination
    start = (page - 1) * limit
    end = start + limit
    sessions = queryset.order_by('-exit_time')[start:end]
    
    data = []
    for session in sessions:
        data.append({
            'id': session.id,
            'license_plate': session.license_plate,
            'entry_time': timezone.localtime(session.entry_time).strftime('%Y-%m-%d %H:%M:%S'),
            'exit_time': timezone.localtime(session.exit_time).strftime('%Y-%m-%d %H:%M:%S'),
            'duration_minutes': session.duration_minutes,
            'fee': int(session.fee),
            'payment_status': session.payment_status,
            'payment_status_display': session.get_payment_status_display()
        })
    
    return JsonResponse({
        'success': True,
        'page': page,
        'limit': limit,
        'total': total,
        'total_pages': (total + limit - 1) // limit,
        'sessions': data
    })


# ==================== API KIỂM TRA TRẠNG THÁI BÃI ĐỖ ====================

@require_http_methods(["GET"])
def parking_availability(request):
    """
    API kiểm tra trạng thái bãi đỗ xe
    
    Returns:
        {
            "success": true,
            "total_slots": 4,
            "occupied_slots": 3,
            "available_slots": 1,
            "is_full": false,
            "occupancy_rate": 0.75,
            "active_vehicles": [
                {
                    "license_plate": "30A12345",
                    "entry_time": "2025-11-20 08:30:00",
                    "duration_minutes": 45
                }
            ]
        }
    """
    MAX_PARKING_SLOTS = 4
    
    # Đếm số xe đang đỗ
    active_sessions = ParkingSession.objects.filter(status='ACTIVE').order_by('entry_time')
    occupied_count = active_sessions.count()
    available_count = MAX_PARKING_SLOTS - occupied_count
    is_full = occupied_count >= MAX_PARKING_SLOTS
    occupancy_rate = occupied_count / MAX_PARKING_SLOTS if MAX_PARKING_SLOTS > 0 else 0
    
    # Lấy danh sách xe đang đỗ
    active_vehicles = []
    for session in active_sessions:
        # Tính thời gian đỗ hiện tại
        now = timezone.now()
        duration = int((now - session.entry_time).total_seconds() / 60)
        
        active_vehicles.append({
            'license_plate': session.license_plate,
            'entry_time': timezone.localtime(session.entry_time).strftime('%Y-%m-%d %H:%M:%S'),
            'duration_minutes': duration,
            'session_id': session.id
        })
    
    return JsonResponse({
        'success': True,
        'total_slots': MAX_PARKING_SLOTS,
        'occupied_slots': occupied_count,
        'available_slots': available_count,
        'is_full': is_full,
        'occupancy_rate': round(occupancy_rate, 2),
        'active_vehicles': active_vehicles
    })


# ==================== API XUẤT BÁO CÁO CSV ====================

@require_http_methods(["GET"])
def export_revenue_csv(request):
    """
    API xuất báo cáo doanh thu ra file CSV
    
    Query Parameters:
        - period: 'day', 'week', 'month', 'year', 'all' (mặc định: 'month')
        - start_date: 'YYYY-MM-DD' (tùy chọn)
        - end_date: 'YYYY-MM-DD' (tùy chọn)
        - status: 'all', 'paid', 'unpaid' (mặc định: 'all')
    
    Returns:
        CSV file download
    """
    import csv
    from django.http import HttpResponse
    
    period = request.GET.get('period', 'month')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    status_filter = request.GET.get('status', 'all')
    
    # Xác định khoảng thời gian
    now = timezone.localtime()
    
    if start_date_str and end_date_str:
        # Custom date range
        try:
            start_time = timezone.make_aware(datetime.strptime(start_date_str, '%Y-%m-%d'))
            end_time = timezone.make_aware(datetime.strptime(end_date_str, '%Y-%m-%d')) + timedelta(days=1)
            filename_suffix = f"{start_date_str}_to_{end_date_str}"
        except ValueError:
            return JsonResponse({'error': 'Định dạng ngày không hợp lệ'}, status=400)
    
    elif period == 'day':
        start_time = timezone.make_aware(datetime.combine(now.date(), datetime.min.time()))
        end_time = start_time + timedelta(days=1)
        filename_suffix = now.strftime('%Y-%m-%d')
    
    elif period == 'week':
        start_time = timezone.make_aware(datetime.combine(now.date() - timedelta(days=now.weekday()), datetime.min.time()))
        end_time = start_time + timedelta(days=7)
        filename_suffix = f"week_{start_time.strftime('%Y-%m-%d')}"
    
    elif period == 'month':
        start_time = timezone.make_aware(datetime(now.year, now.month, 1))
        if now.month == 12:
            end_time = timezone.make_aware(datetime(now.year + 1, 1, 1))
        else:
            end_time = timezone.make_aware(datetime(now.year, now.month + 1, 1))
        filename_suffix = now.strftime('%Y-%m')
    
    elif period == 'year':
        start_time = timezone.make_aware(datetime(now.year, 1, 1))
        end_time = timezone.make_aware(datetime(now.year + 1, 1, 1))
        filename_suffix = str(now.year)
    
    elif period == 'all':
        start_time = None
        end_time = None
        filename_suffix = 'all'
    
    else:
        return JsonResponse({'error': 'Period không hợp lệ'}, status=400)
    
    # Query sessions
    sessions = ParkingSession.objects.filter(status='COMPLETED')
    
    if start_time and end_time:
        sessions = sessions.filter(exit_time__gte=start_time, exit_time__lt=end_time)
    
    # Filter by payment status
    if status_filter == 'paid':
        sessions = sessions.filter(payment_status='PAID')
    elif status_filter == 'unpaid':
        sessions = sessions.filter(payment_status='UNPAID')
    
    sessions = sessions.order_by('-exit_time')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="bao_cao_doanh_thu_{filename_suffix}.csv"'
    
    # Add BOM for Excel UTF-8 support
    response.write('\ufeff')
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'STT',
        'Biển số xe',
        'Thời gian vào',
        'Thời gian ra',
        'Thời lượng (phút)',
        'Phí đỗ xe (VNĐ)',
        'Trạng thái thanh toán',
        'Ngày tạo'
    ])
    
    # Write data
    total_revenue = Decimal(0)
    paid_revenue = Decimal(0)
    unpaid_revenue = Decimal(0)
    
    for idx, session in enumerate(sessions, 1):
        payment_status_map = {
            'PAID': 'Đã thanh toán',
            'UNPAID': 'Chưa thanh toán',
            'FREE': 'Miễn phí'
        }
        
        writer.writerow([
            idx,
            session.license_plate,
            session.entry_time.strftime('%d/%m/%Y %H:%M:%S'),
            session.exit_time.strftime('%d/%m/%Y %H:%M:%S') if session.exit_time else '',
            session.duration_minutes or 0,
            int(session.fee),
            payment_status_map.get(session.payment_status, session.payment_status),
            session.created_at.strftime('%d/%m/%Y %H:%M:%S')
        ])
        
        total_revenue += session.fee
        if session.payment_status == 'PAID':
            paid_revenue += session.fee
        elif session.payment_status == 'UNPAID':
            unpaid_revenue += session.fee
    
    # Write summary
    writer.writerow([])
    writer.writerow(['=== TỔNG KẾT ==='])
    writer.writerow(['Tổng số giao dịch:', sessions.count()])
    writer.writerow(['Tổng doanh thu:', f"{int(total_revenue):,} VNĐ"])
    writer.writerow(['Đã thu:', f"{int(paid_revenue):,} VNĐ"])
    writer.writerow(['Chưa thu:', f"{int(unpaid_revenue):,} VNĐ"])
    writer.writerow(['Ngày xuất báo cáo:', now.strftime('%d/%m/%Y %H:%M:%S')])
    
    return response


@require_http_methods(["GET"])
def export_detections_csv(request):
    """
    API xuất báo cáo phát hiện xe (detections) ra CSV
    
    Query Parameters:
        - days: số ngày quá khứ (mặc định: 7)
        - event_type: 'ENTRY', 'EXIT', 'all' (mặc định: 'all')
    """
    import csv
    from django.http import HttpResponse
    
    days = int(request.GET.get('days', 7))
    event_type = request.GET.get('event_type', 'all')
    
    # Query detections
    start_time = timezone.now() - timedelta(days=days)
    detections = VehicleDetection.objects.filter(detected_at__gte=start_time)
    
    if event_type in ['ENTRY', 'EXIT']:
        detections = detections.filter(event_type=event_type)
    
    detections = detections.order_by('-detected_at')
    
    # Create CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="bao_cao_phat_hien_{days}_ngay.csv"'
    response.write('\ufeff')
    
    writer = csv.writer(response)
    
    # Header
    writer.writerow([
        'STT',
        'Biển số xe',
        'Loại sự kiện',
        'Độ tin cậy (%)',
        'Thời gian phát hiện',
        'Camera nguồn',
        'Đường dẫn ảnh'
    ])
    
    # Data
    for idx, detection in enumerate(detections, 1):
        event_map = {
            'ENTRY': 'Vào bãi',
            'EXIT': 'Ra bãi'
        }
        
        writer.writerow([
            idx,
            detection.license_plate,
            event_map.get(detection.event_type, detection.event_type),
            f"{detection.confidence * 100:.1f}",
            detection.detected_at.strftime('%d/%m/%Y %H:%M:%S'),
            detection.camera_source,
            detection.image_path.name if detection.image_path else ''
        ])
    
    # Summary
    writer.writerow([])
    writer.writerow(['=== TỔNG KẾT ==='])
    writer.writerow(['Tổng số phát hiện:', detections.count()])
    writer.writerow(['Số lần vào:', detections.filter(event_type='ENTRY').count()])
    writer.writerow(['Số lần ra:', detections.filter(event_type='EXIT').count()])
    writer.writerow(['Ngày xuất:', timezone.now().strftime('%d/%m/%Y %H:%M:%S')])
    
    return response
