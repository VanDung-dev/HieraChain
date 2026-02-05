"""Generate validator key for testing"""

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import json

key = Ed25519PrivateKey.generate()
priv = key.private_bytes_raw().hex()
pub = key.public_key().public_bytes_raw().hex()

data = {
    "private_key": priv,
    "public_key": pub
}

with open("validator_key.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Generated validator_key.json")
print(f"Public Key: {pub}")
