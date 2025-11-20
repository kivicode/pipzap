"""Simple test app."""

import requests
import numpy as np
from flask import Flask

app = Flask(__name__)


@app.route("/")
def hello():
    data = np.array([1, 2, 3])
    response = requests.get("https://api.example.com")
    return f"Hello! Data: {data.sum()}, Status: {response.status_code}"
