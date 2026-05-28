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





def get_routepay_token():
    cached_token = cache.get("routepay_access_token")
    if cached_token:
        return cached_token

    response = requests.post(
        settings.ROUTEPAY_AUTH_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": settings.ROUTEPAY_CLIENT_ID,
            "client_secret": settings.ROUTEPAY_CLIENT_SECRET,
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=30,
    )

    response.raise_for_status()
    result = response.json()

    access_token = result.get("access_token")
    expires_in = int(result.get("expires_in", 3600))

    if not access_token:
        raise ValueError("RoutePay token response did not include access_token")

    cache.set("routepay_access_token", access_token, max(expires_in - 120, 300))
    return access_token


@csrf_exempt
@require_POST
def init_routepay_payment(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "message": "Invalid JSON payload."}, status=400)

    payee_id = str(data.get("payeeId") or "").strip()
    amount_raw = data.get("amount")
    email = str(data.get("email") or "no-reply@lera.ng").strip()
    phone = str(data.get("phone") or "").strip()
    customer_name = str(data.get("payeeName") or "LERA Payer").strip()

    first_name = str(data.get("firstName") or customer_name.split(" ")[0] or "LERA").strip()
    last_name = str(data.get("lastName") or "Payer").strip()

    if not payee_id:
        return JsonResponse({"ok": False, "message": "Payee ID is required."}, status=400)

    try:
        amount = Decimal(str(amount_raw))
    except (InvalidOperation, TypeError):
        return JsonResponse({"ok": False, "message": "Invalid amount."}, status=400)

    if amount <= 0:
        return JsonResponse({"ok": False, "message": "Amount must be greater than zero."}, status=400)

    merchant_reference = f"LERA-{payee_id}-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

    return_url = f"{settings.ROUTEPAY_RETURN_URL}?merchantReference={merchant_reference}"

    routepay_payload = {
        "merchantId": settings.ROUTEPAY_CLIENT_ID,
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

    transaction = RoutePayTransaction.objects.create(
        payee_id=payee_id,
        merchant_reference=merchant_reference,
        amount=amount,
        customer_name=customer_name,
        customer_email=email,
        customer_phone=phone,
        metadata=data.get("metadata") or {},
    )

    try:
        token = get_routepay_token()

        response = requests.post(
            f"{settings.ROUTEPAY_BASE_URL}/payment/api/v1/Payment/SetRequest",
            json=routepay_payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )

        result = response.json()
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
        transaction.raw_init_response = {"error": str(exc)}
        transaction.save(update_fields=["raw_init_response", "updated_at"])

        return JsonResponse(
            {
                "ok": False,
                "message": "Unable to initialize RoutePay payment. Please try again.",
            },
            status=500,
        )


@require_GET
def routepay_status(request, transaction_reference):
    try:
        token = get_routepay_token()

        response = requests.get(
            f"{settings.ROUTEPAY_BASE_URL}/payment/api/v1/Payment/GetTransaction/{transaction_reference}",
            headers={
                "Authorization": f"Bearer {token}",
            },
            timeout=30,
        )

        result = response.json()

        payment_status = result.get("paymentStatus")
        payment_description = result.get("paymentDescription") or result.get("description") or ""

        is_successful = (
            response.status_code == 200
            and int(payment_status) == 0
            and payment_description.lower() == "successful"
        )

        RoutePayTransaction.objects.filter(
            transaction_reference=str(transaction_reference)
        ).update(
            payment_status=payment_status,
            payment_description=payment_description,
            raw_status_response=result,
            is_successful=is_successful,
        )

        return JsonResponse(
            {
                "ok": True,
                "isSuccessful": is_successful,
                "paymentStatus": payment_status,
                "paymentDescription": payment_description,
                "routepay": result,
            }
        )

    except Exception:
        return JsonResponse(
            {
                "ok": False,
                "message": "Unable to verify transaction status.",
            },
            status=500,
        )


@require_GET
def routepay_return(request):
    merchant_reference = request.GET.get("merchantReference")

    if not merchant_reference:
        return HttpResponseRedirect("https://lera.odoo.com/payment?payment_status=unknown")

    transaction = RoutePayTransaction.objects.filter(
        merchant_reference=merchant_reference
    ).first()

    if not transaction or not transaction.transaction_reference:
        return HttpResponseRedirect("https://lera.odoo.com/payment?payment_status=pending")

    # Re-query RoutePay before showing success.
    try:
        token = get_routepay_token()

        response = requests.get(
            f"{settings.ROUTEPAY_BASE_URL}/payment/api/v1/Payment/GetTransaction/{transaction.transaction_reference}",
            headers={
                "Authorization": f"Bearer {token}",
            },
            timeout=30,
        )

        result = response.json()

        payment_status = result.get("paymentStatus")
        payment_description = result.get("paymentDescription") or result.get("description") or ""

        is_successful = (
            response.status_code == 200
            and int(payment_status) == 0
            and payment_description.lower() == "successful"
        )

        transaction.payment_status = payment_status
        transaction.payment_description = payment_description
        transaction.raw_status_response = result
        transaction.is_successful = is_successful
        transaction.save()

        if is_successful:
            return HttpResponseRedirect(
                f"https://lera.odoo.com/payment?payment_status=successful&ref={transaction.transaction_reference}"
            )

        return HttpResponseRedirect(
            f"https://lera.odoo.com/payment?payment_status=pending&ref={transaction.transaction_reference}"
        )

    except Exception:
        return HttpResponseRedirect("https://lera.odoo.com/payment?payment_status=verification_failed")
    

