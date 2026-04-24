import os
import httpx
import jwt
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from dataclasses import dataclass


RMF_BASE = os.environ.get("RMF_BASE_URL", "http://localhost:8000")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8317/v1")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "your-api-key-3")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "claude-opus-4-6")
JWT_SECRET = os.environ.get("RMF_JWT_SECRET", "rmfisawesome")

JWT_TOKEN = jwt.encode(
    {"preferred_username": "admin", "iss": "stub", "aud": "rmf_api_server"},
    JWT_SECRET,
    algorithm="HS256",
)

model = OpenAIChatModel(
    OPENAI_MODEL,
    provider=OpenAIProvider(base_url=OPENAI_BASE_URL, api_key=OPENAI_API_KEY),
)


@dataclass
class RmfDeps:
    client: httpx.Client


def make_client() -> httpx.Client:
    return httpx.Client(headers={"Authorization": f"Bearer {JWT_TOKEN}"})
