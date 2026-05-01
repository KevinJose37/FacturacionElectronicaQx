"""Test solo rechazos."""
import urllib.request, json

payload = json.dumps({
    "messages": [{"role": "user", "content": "Cuáles son las facturas rechazadas y por qué?"}]
}).encode()
req = urllib.request.Request(
    "http://localhost:8888/api/chat",
    data=payload,
    headers={"Content-Type": "application/json"},
)
try:
    r = urllib.request.urlopen(req, timeout=60)
    data = json.loads(r.read())
    print(data['content'])
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode()}")
