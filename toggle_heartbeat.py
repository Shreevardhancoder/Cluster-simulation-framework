import requests

node_id = "ac84f6f4-e551-4d6b-9143-1c1f7c3488b5"
url = "http://localhost:5000/api/toggle_simulation"
data = {"node_id": node_id, "simulate": False}

response = requests.post(url, json=data)
print(f"Status code: {response.status_code}")
print(f"Response: {response.json()}")
