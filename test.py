import os
from openai import OpenAI

API_KEY = os.getenv("NVIDIA_API_KEY")
BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL_NAME = "nvidia/riva-translate-4b-instruct-v2"

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

try:
    print("Testing the API connection...")
    completion = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": "Say hello"}],
        max_tokens=50
    )
    print("API Response Successful!")
    print("Received Response:", completion.choices[0].message.content)
except Exception as e:
    print("API Connection Error:", e)