import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

print("Listing available models that support 'generateContent':\n")
try:
    for m in client.models.list():
        supported_actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in supported_actions or "generate_content" in supported_actions:
            name = getattr(m, "name", None)
            display_name = getattr(m, "display_name", None)
            if display_name:
                print(f"- {name} ({display_name})")
            else:
                print(f"- {name}")
except Exception as e:
    print(f"Error: {e}")

print("\nNote: Use the full string (e.g., 'models/gemini-2.5-pro') or just the suffix (e.g., 'gemini-2.5-pro').")