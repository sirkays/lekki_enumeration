import json
from datetime import datetime

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Q

from core.models import LekkiEnumeration, BillDistribution


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_visualizer(request):
    """
    Ensures the authenticated user has visualizer/admin access.
    Returns None if access is allowed, otherwise returns a response.
    """
    try:
        profile = request.user.profile
    except Exception:
        return render(request, 'visualization/403.html', status=403)

    if not profile.is_visualizer:
        return render(request, 'visualization/403.html', status=403)

    return None


# ---------------------------------------------------------------------------
# Authentication Views
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def user_login(request):
    """
    Login page. On success uses Django's built-in session authentication
    and redirects to the visualization dashboard.
    """
    if request.user.is_authenticated:
        return redirect('visualization:visualization')

    error = None

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me') == 'on'

        user = authenticate(request, username=email, password=password)
        if user and user.is_active:
            login(request, user)

            # Session expiry:
            # remember_me checked -> 7 days
            # otherwise -> browser session
            if remember_me:
                request.session.set_expiry(60 * 60 * 24 * 7)  # 7 days
            else:
                request.session.set_expiry(0)  # expire on browser close

            return redirect('visualization:visualization')
        else:
            error = 'Invalid email or password. Please try again.'

    return render(request, 'visualization/login.html', {'error': error})


@require_http_methods(["POST", "GET"])
def user_logout(request):
    """Logs the user out using Django's built-in logout."""
    logout(request)
    return redirect('visualization:user_login')


# ---------------------------------------------------------------------------
# Main Visualization View
# ---------------------------------------------------------------------------

@login_required(login_url='visualization:user_login')
def visualization(request):
    """
    Main visualization dashboard. Requires authenticated user with
    visualizer/admin role. Passes context needed to bootstrap the map/chart UI.
    """
    error_response = _require_visualizer(request)
    if error_response:
        return error_response

    current_year = datetime.now().year
    available_years = list(
        BillDistribution.objects.values_list('year', flat=True)
        .distinct()
        .order_by('-year')
    )
    if current_year not in available_years:
        available_years.insert(0, current_year)

    property_types = list(
        LekkiEnumeration.objects.exclude(property_type__isnull=True)
        .exclude(property_type='')
        .values_list('property_type', flat=True)
        .distinct()
        .order_by('property_type')
    )

    revenue_categories = list(
        LekkiEnumeration.objects.exclude(revenue_category__isnull=True)
        .exclude(revenue_category='')
        .values_list('revenue_category', flat=True)
        .distinct()
        .order_by('revenue_category')
    )

    street_names = list(
        LekkiEnumeration.objects.exclude(street_name__isnull=True)
        .exclude(street_name='')
        .values_list('street_name', flat=True)
        .distinct()
        .order_by('street_name')
    )

    selected_year = int(request.GET.get('year', current_year))
    billed_ids = set(
        BillDistribution.objects.filter(year=selected_year)
        .values_list('property_id', flat=True)
    )

    total_properties = LekkiEnumeration.objects.exclude(
        Q(latitude__isnull=True) | Q(longitude__isnull=True)
    ).count()

    billed_count = LekkiEnumeration.objects.filter(
        property_id__in=billed_ids
    ).count()

    unbilled_count = total_properties - billed_count

    category_stats = list(
        LekkiEnumeration.objects.values('revenue_category')
        .annotate(total=Count('id'))
        .exclude(revenue_category__isnull=True)
        .exclude(revenue_category='')
        .order_by('-total')
    )

    context = {
        'user': request.user,
        'profile': request.user.profile,
        'current_year': current_year,
        'selected_year': selected_year,
        'available_years': available_years,
        'property_types': property_types,
        'revenue_categories': revenue_categories,
        'street_names': street_names,
        'total_properties': total_properties,
        'billed_count': billed_count,
        'unbilled_count': unbilled_count,
        'billed_percentage': round((billed_count / total_properties * 100), 1) if total_properties else 0,
        'category_stats_json': json.dumps(category_stats),
    }
    return render(request, 'visualization/visualization.html', context)


# ---------------------------------------------------------------------------
# API Endpoints (consumed by frontend JS)
# ---------------------------------------------------------------------------

@login_required(login_url='visualization:user_login')
def api_properties(request):
    """
    Returns GeoJSON FeatureCollection of all properties with bill status.
    Query params:
      - year (int): year to check bill status for (default: current year)
      - property_type (str): filter by property type
      - revenue_category (str): filter by revenue category
      - street_name (str): filter by street name
      - status (str): 'billed' | 'unbilled' | '' (all)
      - q (str): free text search on owner_name, property_id, street_name
    """
    error_response = _require_visualizer(request)
    if error_response:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    year = int(request.GET.get('year', datetime.now().year))
    property_type = request.GET.get('property_type', '').strip()
    revenue_category = request.GET.get('revenue_category', '').strip()
    street_name = request.GET.get('street_name', '').strip()
    status_filter = request.GET.get('status', '').strip()
    search_query = request.GET.get('q', '').strip()

    qs = LekkiEnumeration.objects.exclude(
        Q(latitude__isnull=True) | Q(longitude__isnull=True)
    )

    if property_type:
        qs = qs.filter(property_type=property_type)

    if revenue_category:
        qs = qs.filter(revenue_category=revenue_category)

    if street_name:
        qs = qs.filter(street_name__icontains=street_name)

    if search_query:
        qs = qs.filter(
            Q(owner_name__icontains=search_query) |
            Q(property_id__icontains=search_query) |
            Q(street_name__icontains=search_query) |
            Q(house_number__icontains=search_query) |
            Q(business_name_1__icontains=search_query)
        )

    billed_ids = set(
        BillDistribution.objects.filter(year=year)
        .values_list('property_id', flat=True)
    )

    if status_filter == 'billed':
        qs = qs.filter(property_id__in=billed_ids)
    elif status_filter == 'unbilled':
        qs = qs.exclude(property_id__in=billed_ids)

    features = []
    for prop in qs.values(
        'id', 'property_id', 'street_name', 'house_number',
        'property_type', 'owner_name', 'owner_phone', 'owner_email',
        'business_type', 'no_of_floors', 'no_of_units',
        'revenue_category', 'latitude', 'longitude',
        'completeness_status', 'enumeration_date',
        'photo_front', 'photo_gate', 'photo_signage', 'photo_street',
        'business_name_1', 'business_name_2', 'contact_name', 'contact_phone',
        'confirmed_house_number', 'assigned_house_number',
    ):
        is_billed = prop['property_id'] in billed_ids

        bill_image_url = None
        bill_date = None
        if is_billed:
            try:
                bill = BillDistribution.objects.filter(
                    property_id=prop['property_id'],
                    year=year
                ).select_related('captured_by').first()

                if bill and bill.bill_image:
                    bill_image_url = bill.bill_image.url
                    bill_date = bill.date_captured.strftime('%Y-%m-%d %H:%M') if bill.date_captured else None
            except Exception:
                pass

        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [prop['longitude'], prop['latitude']],
            },
            'properties': {
                **prop,
                'is_billed': is_billed,
                'bill_image_url': bill_image_url,
                'bill_date': bill_date,
            }
        })

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': features,
        'meta': {
            'total': len(features),
            'billed': sum(1 for f in features if f['properties']['is_billed']),
            'year': year,
        }
    })


@login_required(login_url='visualization:user_login')
def api_chart_data(request):
    """Returns aggregated data for the chart view."""
    error_response = _require_visualizer(request)
    if error_response:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    year = int(request.GET.get('year', datetime.now().year))

    billed_ids = set(
        BillDistribution.objects.filter(year=year)
        .values_list('property_id', flat=True)
    )

    by_category = []
    for item in (
        LekkiEnumeration.objects
        .exclude(revenue_category__isnull=True)
        .exclude(revenue_category='')
        .values('revenue_category')
        .annotate(total=Count('id'))
        .order_by('-total')
    ):
        billed = LekkiEnumeration.objects.filter(
            revenue_category=item['revenue_category'],
            property_id__in=billed_ids,
        ).count()

        by_category.append({
            'label': item['revenue_category'],
            'total': item['total'],
            'billed': billed,
            'unbilled': item['total'] - billed,
        })

    # ── NEW: add the uncategorized bucket ──────────────────────────────────
    uncategorized_qs = LekkiEnumeration.objects.filter(
        Q(revenue_category__isnull=True) | Q(revenue_category='')
    )
    uncategorized_total = uncategorized_qs.count()
    if uncategorized_total > 0:
        uncategorized_billed = uncategorized_qs.filter(
            property_id__in=billed_ids
        ).count()
        by_category.append({
            'label': '',        # empty string → frontend barColors() picks light blue
            'total': uncategorized_total,
            'billed': uncategorized_billed,
            'unbilled': uncategorized_total - uncategorized_billed,
        })
    # ───────────────────────────────────────────────────────────────────────

    by_type = []
    for item in (
        LekkiEnumeration.objects
        .exclude(property_type__isnull=True)
        .exclude(property_type='')
        .values('property_type')
        .annotate(total=Count('id'))
        .order_by('-total')[:10]
    ):
        billed = LekkiEnumeration.objects.filter(
            property_type=item['property_type'],
            property_id__in=billed_ids,
        ).count()

        by_type.append({
            'label': item['property_type'],
            'total': item['total'],
            'billed': billed,
            'unbilled': item['total'] - billed,
        })

    current_year = datetime.now().year
    yearly_trend = []
    for y in range(current_year - 4, current_year + 1):
        count = BillDistribution.objects.filter(year=y).count()
        yearly_trend.append({'year': y, 'bills': count})

    return JsonResponse({
        'by_category': by_category,
        'by_type': by_type,
        'yearly_trend': yearly_trend,
    })


def test_set(request):
    data = LekkiEnumeration.objects.filter(revenue_category__isnull=True).count()
    print(data, " map....")
    return JsonResponse({})


