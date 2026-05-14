"""Generate a local dev JWT for testing — signs with test-secret, NOT for production."""
import base64, json, hmac, hashlib, time

merchant_id = input("Merchant UUID (or press Enter for default): ").strip()
if not merchant_id:
    merchant_id = "fc26736f-6ad1-4d75-a99f-511542226eba"

email = input("Email (or press Enter for default): ").strip()
if not email:
    email = "test@test.com"

header = base64.urlsafe_b64encode(
    json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
).rstrip(b"=").decode()

payload = base64.urlsafe_b64encode(
    json.dumps({
        "sub": merchant_id,
        "merchant_id": merchant_id,
        "email": email,
        "role": "merchant",
        "exp": int(time.time()) + 60 * 60 * 24 * 365,
    }).encode()
).rstrip(b"=").decode()

signature = base64.urlsafe_b64encode(
    hmac.new(b"test-secret", f"{header}.{payload}".encode(), hashlib.sha256).digest()
).rstrip(b"=").decode()

print("\nBEARER TOKEN:")
print(f"{header}.{payload}.{signature}")
print("\nPaste this in the frontend Settings page or as Authorization: Bearer <token>")
