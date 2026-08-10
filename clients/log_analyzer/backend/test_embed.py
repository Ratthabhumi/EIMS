import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={API_KEY}"
payload = {
    "model": "models/text-embedding-004",
    "content": {
        "parts": [{
            "text": "Hello world"
        }]
    }
}
headers = {'Content-Type': 'application/json'}
response = requests.post(url, headers=headers, json=payload)
print(response.status_code)
data = response.json()
if "embedding" in data:
    print(len(data["embedding"]["values"]))
else:
    print(data)
