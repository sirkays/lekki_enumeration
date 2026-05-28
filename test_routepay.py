import os
import json
import uuid
import requests
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================
# Change ENVIRONMENT to one of: "qa", "dev", "prod"
ENVIRONMENT = os.getenv("ROUTEPAY_ENVIRONMENT", "qa").lower()

CLIENT_ID = os.getenv("ROUTEPAY_CLIENT_ID", "vUBxwsvafqUFfCn").strip()
CLIENT_SECRET = os.getenv("ROUTEPAY_CLIENT_SECRET", "HedwxvsfFsPoKWRcLqvaXFERvAjrlt").strip()

RETURN_URL = os.getenv(
    "ROUTEPAY_RETURN_URL",
    "https://leravirtualization.newwavesecosystem.com/authapp/api/routepay/return/"
)

ENVIRONMENTS = {
    "qa": {
        "auth_url": "https://authqa.routepay.com/connect/token",
        "base_url": "https://apiqa.routepay.com",
    },
    "dev": {
        "auth_url": "https://authdev.routepay.com/connect/token",
        "base_url": "https://apidev.routepay.com",
    },
    "prod": {
        "auth_url": "https://auth.routepay.com/connect/token",
        "base_url": "https://api.routepay.com",
    },
}

if ENVIRONMENT not in ENVIRONMENTS:
    raise ValueError("Invalid ROUTEPAY_ENVIRONMENT. Use qa, dev, or prod.")

AUTH_URL = ENVIRONMENTS[ENVIRONMENT]["auth_url"]
BASE_URL = ENVIRONMENTS[ENVIRONMENT]["base_url"]


# ============================================================
# SAFETY CHECKS
# ============================================================
if not CLIENT_ID:
    raise ValueError("ROUTEPAY_CLIENT_ID is not set.")

if not CLIENT_SECRET:
    raise ValueError("ROUTEPAY_CLIENT_SECRET is not set.")


def print_section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def safe_json(response):
    try:
        return response.json()
    except Exception:
        return {
            "raw_response": response.text
        }


# ============================================================
# 1. GET ROUTEPAY TOKEN
# ============================================================
def get_token():
    print_section("1. TESTING ROUTEPAY TOKEN ENDPOINT")

    print("Environment:", ENVIRONMENT)
    print("Auth URL:", AUTH_URL)
    print("Base URL:", BASE_URL)
    print("Client ID Length:", len(CLIENT_ID))
    print("Client Secret Length:", len(CLIENT_SECRET))

    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "User-Agent": "LERA-RoutePay-Test/1.0",
    }

    response = requests.post(
        AUTH_URL,
        data=payload,
        headers=headers,
        timeout=30,
    )

    result = safe_json(response)

    print("Token Status Code:", response.status_code)
    print("Token Response:")
    print(json.dumps(result, indent=2))

    if response.status_code != 200:
        raise RuntimeError("Token request failed.")

    access_token = result.get("access_token")

    if not access_token:
        raise RuntimeError("No access_token returned by RoutePay.")

    print("Access token received successfully.")
    return access_token


# ============================================================
# 2. CREATE PAYMENT REQUEST
# ============================================================
def create_payment(access_token):
    print_section("2. TESTING ROUTEPAY PAYMENT SETREQUEST ENDPOINT")

    endpoint = f"{BASE_URL}/payment/api/v1/Payment/SetRequest"

    merchant_reference = (
        "LERA-TEST-"
        + datetime.now().strftime("%Y%m%d%H%M%S")
        + "-"
        + uuid.uuid4().hex[:6].upper()
    )

    return_url = f"{RETURN_URL}?merchantReference={merchant_reference}"

    payload = {
        "merchantId": CLIENT_ID,
        "returnUrl": return_url,
        "merchantReference": merchant_reference,
        "totalAmount": "100",
        "currency": "NGN",
        "paymentType": "PAYMENT",
        "customer": {
            "email": "test@example.com",
            "mobile": "08000000000",
            "firstname": "Test",
            "lastname": "User",
            "username": "TEST001",
        },
        "products": [
            {
                "name": "LERA Test Payment",
                "unitPrice": "100",
                "quantity": 1,
            }
        ],
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "LERA-RoutePay-Test/1.0",
    }

    print("Payment Endpoint:", endpoint)
    print("Payment Payload:")
    print(json.dumps(payload, indent=2))

    response = requests.post(
        endpoint,
        json=payload,
        headers=headers,
        timeout=30,
    )

    result = safe_json(response)

    print("Payment Status Code:", response.status_code)
    print("Payment Response:")
    print(json.dumps(result, indent=2))

    if response.status_code != 200:
        raise RuntimeError("Payment SetRequest failed.")

    redirect_url = result.get("redirectUrl")
    transaction_reference = result.get("transactionReference")

    if not redirect_url:
        raise RuntimeError("No redirectUrl returned by RoutePay.")

    print("\nPayment initialized successfully.")
    print("Redirect URL:", redirect_url)
    print("Transaction Reference:", transaction_reference)
    print("Merchant Reference:", merchant_reference)

    return transaction_reference


# ============================================================
# 3. QUERY PAYMENT STATUS
# ============================================================
def query_transaction(access_token, transaction_reference):
    if not transaction_reference:
        print("No transaction reference to query.")
        return

    print_section("3. TESTING ROUTEPAY GETTRANSACTION ENDPOINT")

    endpoint = f"{BASE_URL}/payment/api/v1/Payment/GetTransaction/{transaction_reference}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": "LERA-RoutePay-Test/1.0",
    }

    print("Query Endpoint:", endpoint)

    response = requests.get(
        endpoint,
        headers=headers,
        timeout=30,
    )

    result = safe_json(response)

    print("Query Status Code:", response.status_code)
    print("Query Response:")
    print(json.dumps(result, indent=2))


# ============================================================
# RUN TEST
# ============================================================
if __name__ == "__main__":
    try:
        token = get_token()
        transaction_ref = create_payment(token)
        query_transaction(token, transaction_ref)

    except Exception as exc:
        print_section("TEST FAILED")
        print("Error:", str(exc))