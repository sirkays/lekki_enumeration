import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lekki_project.settings')
django.setup()

from django.test import Client

client = Client()
response = client.post(
    '/authapp/api/routepay/init-payment/',
    json.dumps({
        "payeeId": "6A2FF15AA6EE6",
        "amount": 1000,
        "email": "test@example.com",
        "phone": "08012345678",
        "payeeName": "Test User",
    }),
    content_type='application/json'
)

print(f"Status Code: {response.status_code}")
print("Response Body:")
try:
    print(json.dumps(response.json(), indent=2))
except Exception:
    print(response.content.decode('utf-8'))
