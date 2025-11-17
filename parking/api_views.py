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
