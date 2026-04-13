from django.db.models import Q, Count
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    parser_classes,
)
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authapp.authentication import SessionTokenAuthentication
from .models import LekkiEnumeration, BillDistribution
from .serializers import LekkiEnumerationSerializer, BillDistributionSerializer


# ── Add this view to core/views.py ───────────────────────────────────────────

@api_view(['GET'])
@authentication_classes([SessionTokenAuthentication])
@permission_classes([IsAuthenticated])
def get_available_years(request):
    """
    Returns the list of years that have at least one BillDistribution record,
    always including the current year even if no bills exist yet.

    Response: { "years": [2026, 2025, 2024] }   (descending order)
    """
    from django.utils import timezone

    current_year = timezone.now().year

    years = list(
        BillDistribution.objects
        .values_list('year', flat=True)
        .distinct()
        .order_by('-year')
    )

    if current_year not in years:
        years.insert(0, current_year)

    return Response({'years': years})


@api_view(['GET'])
@authentication_classes([SessionTokenAuthentication])
@permission_classes([IsAuthenticated])
def get_properties(request):
    search_query = request.query_params.get('search', '').strip()
    year = request.query_params.get('year', None)

    from django.utils import timezone
    try:
        year = int(year) if year else timezone.now().year
    except (TypeError, ValueError):
        year = timezone.now().year

    if search_query:
        properties = LekkiEnumeration.objects.filter(
            Q(property_id__icontains=search_query) |
            Q(street_name__icontains=search_query) |
            Q(owner_name__icontains=search_query) |
            Q(owner_phone__icontains=search_query) |
            Q(contact_phone__icontains=search_query) |
            Q(business_name_1__icontains=search_query)
        )[:30]
    else:
        properties = LekkiEnumeration.objects.filter(
            property_id__isnull=False,
            latitude__isnull=False,
            longitude__isnull=False,
        )[:20]

    # Fetch all billed property IDs for the requested year in one query.
    billed_ids = set(
        BillDistribution.objects
        .filter(year=year)
        .values_list('property_id', flat=True)
    )

    serializer = LekkiEnumerationSerializer(properties, many=True)
    data = serializer.data

    # Stamp each property with is_billed without touching the serializer class.
    for item in data:
        item['is_billed'] = item.get('property_id') in billed_ids

    return Response(data)

@api_view(['POST'])
@authentication_classes([SessionTokenAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
@transaction.atomic
def capture_bill(request):
    lekki_enum_id = request.data.get('lekki_enum_id')
    property_id = request.data.get('property_id')
    year = request.data.get('year')
    bill_image = request.FILES.get('bill_image')

    if not all([lekki_enum_id, property_id, year, bill_image]):
        return Response(
            {
                "detail": "Missing required fields: lekki_enum_id, property_id, year, or bill_image."
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        year = int(year)
    except (TypeError, ValueError):
        return Response(
            {"detail": "Year must be a valid integer."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    lekki_enum = get_object_or_404(LekkiEnumeration, property_id=lekki_enum_id)

    if lekki_enum.property_id != property_id:
        return Response(
            {"detail": "The provided property_id does not match the selected property."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if BillDistribution.objects.filter(lekki_enum=lekki_enum, year=year).exists():
        return Response(
            {"detail": f"A bill for {property_id} has already been distributed for {year}."},
            status=status.HTTP_409_CONFLICT,
        )

    latitude = request.data.get('latitude')
    longitude = request.data.get('longitude')

    try:
        latitude = float(latitude) if latitude not in [None, ''] else None
    except (TypeError, ValueError):
        latitude = None

    try:
        longitude = float(longitude) if longitude not in [None, ''] else None
    except (TypeError, ValueError):
        longitude = None

    distribution = BillDistribution.objects.create(
        lekki_enum=lekki_enum,
        property_id=property_id,
        year=year,
        bill_image=bill_image,
        captured_by=request.user,
        latitude=latitude,
        longitude=longitude,
    )

    serializer = BillDistributionSerializer(distribution)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([SessionTokenAuthentication])
@permission_classes([IsAuthenticated])
def get_property_bills(request, property_id):
    bills = BillDistribution.objects.filter(
        lekki_enum__property_id=property_id
    ).select_related('lekki_enum', 'captured_by').order_by('-date_captured')

    serializer = BillDistributionSerializer(bills, many=True)
    return Response(serializer.data)




@api_view(['GET'])
@authentication_classes([SessionTokenAuthentication])
@permission_classes([IsAuthenticated])
def tasks_dashboard(request):
    """
    Returns dashboard summary and recent completed bill distribution tasks.

    Optional query params:
    - year=2026
    - limit=20
    - mine=true   -> only bills uploaded by current logged-in user
    - start_date=2026-01-01
    - end_date=2026-12-31
    """
    now = timezone.now()
    year = request.query_params.get('year')
    limit = request.query_params.get('limit', 20)
    mine = request.query_params.get('mine', '').lower()
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20

    if year:
        try:
            year = int(year)
        except ValueError:
            return Response(
                {"detail": "year must be a valid integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        year = now.year

    qs = BillDistribution.objects.filter(year=year).select_related('lekki_enum', 'captured_by')

    if mine in ['true', '1', 'yes']:
        qs = qs.filter(captured_by=request.user)

    if start_date:
        try:
            qs = qs.filter(date_captured__date__gte=start_date)
        except Exception:
            return Response(
                {"detail": "start_date must be in YYYY-MM-DD format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if end_date:
        try:
            qs = qs.filter(date_captured__date__lte=end_date)
        except Exception:
            return Response(
                {"detail": "end_date must be in YYYY-MM-DD format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    total_distribution = qs.count()
    active_agents = qs.exclude(captured_by__isnull=True).values('captured_by').distinct().count()

    total_properties = LekkiEnumeration.objects.exclude(property_id__isnull=True).exclude(property_id='').count()
    efficiency_rate = round((total_distribution / total_properties) * 100, 1) if total_properties > 0 else 0.0

    recent = qs.order_by('-date_captured')[:limit]
    recent_data = BillDistributionSerializer(recent, many=True).data

    today_count = qs.filter(date_captured__date=now.date()).count()
    last_7_days_count = qs.filter(date_captured__date__gte=now.date() - timezone.timedelta(days=6)).count()

    return Response({
        "year": year,
        "filters": {
            "mine": mine in ['true', '1', 'yes'],
            "limit": limit,
            "start_date": start_date,
            "end_date": end_date,
        },
        "summary": {
            "total_distribution": total_distribution,
            "active_agents": active_agents,
            "efficiency_rate": efficiency_rate,
            "today_count": today_count,
            "last_7_days_count": last_7_days_count,
            "total_properties": total_properties,
        },
        "recent_completions": recent_data,
    })
    
