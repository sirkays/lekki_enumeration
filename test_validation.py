import requests
import json

url = "https://lera-billing-api.newwavesecosystem.com/api/etz/validation"
ids = ["6A300C1ACFFEA", "6A2FF15AA6EE6"]

for payee_id in ids:
    full_url = f"{url}?PAYEE_ID={payee_id}"
    print(f"Testing ID: {payee_id}")
    try:
        response = requests.get(full_url)
        print(f"Status Code: {response.status_code}")
        print("Response Body:")
        try:
            print(json.dumps(response.json(), indent=2))
        except Exception:
            print(response.text)
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 40)
