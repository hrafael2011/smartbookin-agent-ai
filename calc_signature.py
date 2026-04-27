import hmac
import hashlib
import sys

payload = sys.argv[1].encode()
secret = "9fe70b0df842599660c29812b9647a36".encode()

signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
print(f"sha256={signature}")
