import requests

url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

data = {
    "username": "martinezgamez.antonio@gmail.com",
    "password": "4528Educacion%$",
    "grant_type": "password",
    "client_id": "cdse-public"
}

response = requests.post(url, data=data)

if response.status_code == 200:
    print("¡Éxito! Tu Token es:")
    print(response.json().get("access_token"))
else:
    print(f"Error {response.status_code}: {response.text}")