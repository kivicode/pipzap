import requests
import json

def fetch_data():
    response = requests.get('https://api.example.com')
    return json.loads(response.text)
