from django.shortcuts import render
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse, HttpResponseRedirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
    parser_classes,
)

from rest_framework_api_key.permissions import HasAPIKey

from authapp.authentication import SessionTokenAuthentication
from .models import SessionToken, UserProfile, RoutePayTransaction
from .serializers import CurrentUserSerializer

import json
import uuid
from decimal import Decimal, InvalidOperation

import requests

User = get_user_model()



@api_view(['GET'])
@authentication_classes([SessionTokenAuthentication])
@permission_classes([IsAuthenticated])
def current_user_profile(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    serializer = CurrentUserSerializer(request.user, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@authentication_classes([SessionTokenAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_profile_image(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    image = request.FILES.get('profile_image')
    if not image:
        return Response(
            {"detail": "profile_image is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    profile.profile_image = image
    profile.save()

    serializer = CurrentUserSerializer(request.user, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([HasAPIKey])
@authentication_classes([])  # API key only for this specific endpoint
def signin(request):
    # Retrieve credentials from the request body
    identifier = request.data.get("identifier")
    password = request.data.get("password")

    if not identifier or not password:
        return Response(
            {"detail": "Both 'identifier' (email or user_id) and 'password' are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Search for user by either email OR user_id
    user = User.objects.filter(Q(email=identifier) | Q(user_id=identifier)).first()

    # Verify user exists and password is correct
    if user is None or not user.check_password(password):
        return Response(
            {"detail": "Invalid credentials."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Ensure the account hasn't been disabled
    if not user.is_active:
        return Response(
            {"detail": "User account is disabled."},
            status=status.HTTP_403_FORBIDDEN
        )

    # Generate the session token using your custom model's class method
    token = SessionToken.create_for_user(user)

    # Return the token to the client
    return Response(
        {
            "message": "Authentication successful.",
            "session_token": token.key,
            "expires_at": token.expires_at,
            "user": {
                "user_id": user.user_id,
                "email": user.email
            }
        },
        status=status.HTTP_200_OK
    )


import time
from urllib.parse import urlencode

def parse_routepay_json(response):
    try:
        return response.json()
    except Exception:
        return {"raw_response": response.text}


def get_routepay_token(agency=""):
    cache_key = f"routepay_access_token_{agency}" if agency else "routepay_access_token"
    cached_token = cache.get(cache_key)
    if cached_token:
        return cached_token

    url = settings.ROUTEPAY_AUTH_URL
    if agency.upper() == "ALPHACEN":
        client_id = getattr(settings, "ALPHACEN_ROUTEPAY_CLIENT_ID", settings.ROUTEPAY_CLIENT_ID)
        client_secret = getattr(settings, "ALPHACEN_ROUTEPAY_CLIENT_SECRET", settings.ROUTEPAY_CLIENT_SECRET)
    else:
        client_id = settings.ROUTEPAY_CLIENT_ID
        client_secret = settings.ROUTEPAY_CLIENT_SECRET

    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "LERA-RoutePay-Integration/1.0",
    }

    try:
        response = requests.post(url, data=payload, headers=headers, timeout=30)
        result = parse_routepay_json(response)
    except Exception as e:
        raise ValueError(f"RoutePay connection failed: {str(e)}")

    if response.status_code != 200:
        raise ValueError(
            f"RoutePay token request failed. Status={response.status_code}. Response={result}"
        )

    access_token = result.get("access_token")
    if not access_token:
        raise ValueError(f"RoutePay token response did not include access_token. Response={result}")

    expires_in = int(result.get("expires_in") or 900)
    cache_duration = max(expires_in - 60, 300)
    cache.set(cache_key, access_token, cache_duration)
    return access_token


def is_routepay_successful(response, result):
    if response.status_code != 200:
        return False

    payment_status = result.get("paymentStatus")
    payment_description = get_routepay_payment_description(result)

    status_str = str(payment_status).strip().lower() if payment_status is not None else ""
    desc_str = str(payment_description).strip().lower()

    success_markers = {"0", "successful", "success", "paid", "approved", "completed"}

    if status_str in success_markers or desc_str in success_markers:
        return True

    return False


def normalize_routepay_status_code(result, is_successful=False):
    if is_successful:
        return 0

    payment_status = result.get("paymentStatus")
    if payment_status is None:
        return None

    status_str = str(payment_status).strip().lower()

    if status_str in {"0", "successful", "success", "paid", "approved", "completed"}:
        return 0
    elif status_str in {"250", "pending"}:
        return 250
    elif status_str in {"260", "processing"}:
        return 260
    elif status_str in {"210", "alreadyprocessed", "already processed"}:
        return 210
    elif status_str in {"220", "cancelled", "canceled"}:
        return 220
    elif status_str in {"550", "failed", "declined"}:
        return 550

    try:
        return int(status_str)
    except ValueError:
        return None


def get_routepay_payment_description(result):
    if not isinstance(result, dict):
        return ""

    for key in ["paymentDescription", "description", "paymentStatus", "responseMessage"]:
        val = result.get(key)
        if val is not None and str(val).strip() != "":
            return str(val).strip()

    return ""


def query_routepay_transaction(transaction_reference, agency=""):
    token = get_routepay_token(agency)
    url = f"{settings.ROUTEPAY_BASE_URL}/payment/api/v1/Payment/GetTransaction/{transaction_reference}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "LERA-RoutePay-Integration/1.0",
    }
    response = requests.get(url, headers=headers, timeout=30)
    result = parse_routepay_json(response)
    return response, result


def save_routepay_status(transaction, response, result):
    is_successful = is_routepay_successful(response, result)
    payment_status = normalize_routepay_status_code(result, is_successful=is_successful)
    payment_description = get_routepay_payment_description(result)

    transaction.payment_status = payment_status
    transaction.payment_description = payment_description
    transaction.raw_status_response = result
    transaction.is_successful = is_successful
    transaction.save()

    return is_successful


@csrf_exempt
@require_POST
def init_routepay_payment(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "message": "Invalid JSON payload."}, status=400)

    payee_id = str(data.get("payeeId") or "").strip()
    agency = str(data.get("agency") or "").strip()
    amount_raw = data.get("amount")
    email = str(data.get("email") or "").strip()
    phone = str(data.get("phone") or "").strip()
    customer_name = str(data.get("payeeName") or "").strip()

    first_name = str(data.get("firstName") or "").strip()
    last_name = str(data.get("lastName") or "").strip()

    if not payee_id:
        return JsonResponse({"ok": False, "message": "Payee ID is required."}, status=400)
    if not email:
        return JsonResponse({"ok": False, "message": "Email is required."}, status=400)
    if not phone:
        return JsonResponse({"ok": False, "message": "Phone number is required."}, status=400)
    if not customer_name:
        return JsonResponse({"ok": False, "message": "Payee name is required."}, status=400)
    if not first_name:
        return JsonResponse({"ok": False, "message": "First name is required."}, status=400)
    if not last_name:
        return JsonResponse({"ok": False, "message": "Last name is required."}, status=400)

    try:
        amount = Decimal(str(amount_raw))
    except (InvalidOperation, TypeError):
        return JsonResponse({"ok": False, "message": "Invalid amount."}, status=400)

    if amount <= 0:
        return JsonResponse({"ok": False, "message": "Amount must be greater than zero."}, status=400)

    merchant_reference = f"LERA-{payee_id}-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

    return_base_url = settings.ROUTEPAY_RETURN_URL.rstrip("/")
    return_url = f"{return_base_url}/{merchant_reference}/"

    if agency.upper() == "ALPHACEN":
        client_id = getattr(settings, "ALPHACEN_ROUTEPAY_CLIENT_ID", settings.ROUTEPAY_CLIENT_ID)
    else:
        client_id = settings.ROUTEPAY_CLIENT_ID

    routepay_payload = {
        "merchantId": client_id,
        "returnUrl": return_url,
        "merchantReference": merchant_reference,
        "totalAmount": str(amount),
        "currency": "NGN",
        "paymentType": "PAYMENT",
        "customer": {
            "email": email,
            "mobile": phone,
            "firstname": first_name,
            "lastname": last_name,
            "username": payee_id,
        },
        "products": [
            {
                "name": f"LERA Property & Community Support Levy - {payee_id}",
                "unitPrice": str(amount),
                "quantity": 1,
            }
        ],
    }

    metadata = data.get("metadata") or {}
    metadata["agency"] = agency

    transaction = RoutePayTransaction.objects.create(
        payee_id=payee_id,
        merchant_reference=merchant_reference,
        amount=amount,
        customer_name=customer_name,
        customer_email=email,
        customer_phone=phone,
        metadata=metadata,
        routepay_payload=routepay_payload,
    )

    try:
        token = get_routepay_token(agency)

        response = requests.post(
            f"{settings.ROUTEPAY_BASE_URL}/payment/api/v1/Payment/SetRequest",
            json=routepay_payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "LERA-RoutePay-Integration/1.0",
            },
            timeout=30,
        )

        result = parse_routepay_json(response)
        transaction.raw_init_response = result

        redirect_url = result.get("redirectUrl")
        transaction_reference = result.get("transactionReference")

        if transaction_reference:
            transaction.transaction_reference = transaction_reference

        transaction.save()

        if response.status_code != 200 or not redirect_url:
            return JsonResponse(
                {
                    "ok": False,
                    "message": "RoutePay payment initialization failed.",
                    "routepay": result,
                },
                status=400,
            )

        return JsonResponse(
            {
                "ok": True,
                "redirectUrl": redirect_url,
                "transactionReference": transaction_reference,
                "merchantReference": merchant_reference,
            }
        )

    except Exception as exc:
        transaction.raw_init_response = {
            "error": str(exc),
            "error_type": exc.__class__.__name__,
        }
        transaction.save(update_fields=["raw_init_response", "updated_at"])

        return JsonResponse(
            {
                "ok": False,
                "message": "Unable to initialize RoutePay payment. Please try again.",
                "debug": str(exc),
            },
            status=500,
        )


@require_GET
def routepay_status(request, transaction_reference):
    try:
        transaction = RoutePayTransaction.objects.filter(
            transaction_reference=transaction_reference
        ).first()

        agency = transaction.metadata.get("agency", "") if transaction and transaction.metadata else ""
        response, result = query_routepay_transaction(transaction_reference, agency)

        if transaction:
            is_successful = save_routepay_status(transaction, response, result)
        else:
            is_successful = is_routepay_successful(response, result)

        payment_status = normalize_routepay_status_code(result, is_successful=is_successful)
        payment_description = get_routepay_payment_description(result)

        return JsonResponse(
            {
                "ok": True,
                "isSuccessful": is_successful,
                "paymentStatus": payment_status,
                "paymentDescription": payment_description,
                "routepay": result,
            }
        )

    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "message": "Unable to verify transaction status.",
                "debug": str(exc),
            },
            status=500,
        )


@require_GET
def routepay_return(request, merchant_reference=None):
    if not merchant_reference:
        merchant_reference = request.GET.get("merchantReference")

    odoo_base_url = getattr(settings, "ODOO_PAYMENT_PAGE_URL", "https://lera.odoo.com/payment")

    if not merchant_reference:
        params = {"payment_status": "pending"}
        return HttpResponseRedirect(f"{odoo_base_url}?{urlencode(params)}")

    transaction = RoutePayTransaction.objects.filter(
        merchant_reference=merchant_reference
    ).first()

    if not transaction:
        params = {"payment_status": "pending", "merchantReference": merchant_reference}
        return HttpResponseRedirect(f"{odoo_base_url}?{urlencode(params)}")

    if not transaction.transaction_reference:
        params = {
            "payment_status": "pending",
            "merchantReference": merchant_reference,
        }
        return HttpResponseRedirect(f"{odoo_base_url}?{urlencode(params)}")

    agency = transaction.metadata.get("agency", "") if transaction and transaction.metadata else ""
    is_successful = False
    last_exc = None

    for attempt in range(5):
        try:
            response, result = query_routepay_transaction(transaction.transaction_reference, agency)
            is_successful = save_routepay_status(transaction, response, result)

            if is_successful:
                break

            time.sleep(2)
        except Exception as exc:
            last_exc = exc
            time.sleep(2)

    try:
        if last_exc and not is_successful:
            params = {
                "payment_status": "verification_failed",
                "ref": transaction.transaction_reference,
                "merchantReference": merchant_reference,
            }
            return HttpResponseRedirect(f"{odoo_base_url}?{urlencode(params)}")

        if is_successful:
            params = {
                "payment_status": "successful",
                "ref": transaction.transaction_reference,
                "merchantReference": merchant_reference,
            }
        else:
            params = {
                "payment_status": "pending",
                "ref": transaction.transaction_reference,
                "merchantReference": merchant_reference,
            }

        return HttpResponseRedirect(f"{odoo_base_url}?{urlencode(params)}")

    except Exception:
        params = {
            "payment_status": "verification_failed",
            "ref": transaction.transaction_reference or "",
            "merchantReference": merchant_reference,
        }
        return HttpResponseRedirect(f"{odoo_base_url}?{urlencode(params)}")

    

