"""Boot the API and serve one request, like a fresh worker after a deploy.
usage: python apps/first_request.py METHOD PATH [MODULE]   (MODULE: api or api_lazy)"""
import importlib
import sys

from fastapi.testclient import TestClient

method, path = sys.argv[1], sys.argv[2]
api = importlib.import_module(sys.argv[3] if len(sys.argv) > 3 else "api")
response = TestClient(api.app).request(method, path, json={"name": "x"} if method == "POST" else None)
print(response.status_code, response.json())
sys.exit(0 if response.status_code == 200 else 1)
