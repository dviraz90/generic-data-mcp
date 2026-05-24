import json
import urllib.error
import urllib.request

from .base import BaseEmbedder
from ..exceptions import EmbedError


class HttpEmbedder(BaseEmbedder):
    def __init__(self, url: str, model: str, api_key: str | None = None):
        self._url = url
        self._model = model
        self._api_key = api_key

    @property
    def model_name(self) -> str:
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        payload = json.dumps({"input": texts, "model": self._model}).encode()
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        req = urllib.request.Request(
            self._url, data=payload, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise EmbedError(f"Embedding API returned {e.code}: {e.reason}") from e
        except Exception as e:
            raise EmbedError(f"Embedding request failed: {e}") from e

        if "data" not in body:
            raise EmbedError(f"Unexpected embedding API response: {body}")

        return [item["embedding"] for item in body["data"]]
