import json


class BedrockEmbedder:
    def __init__(self, bedrock_runtime, model_id: str, dim: int = 1024):
        self._client, self._model_id, self._dim = bedrock_runtime, model_id, dim

    def embed(self, text: str) -> list[float]:
        # normalize=True -> unit vectors, so L2 distance maps cleanly to cosine similarity
        body = json.dumps({"inputText": text[:8000], "dimensions": self._dim, "normalize": True})
        resp = self._client.invoke_model(modelId=self._model_id, body=body, contentType="application/json", accept="application/json")
        return json.loads(resp["body"].read())["embedding"]

