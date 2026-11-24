from urllib.parse import urlparse

import boto3
from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection

from app.domain import RetrievedChunk
from app.generation.base import Embedder


def make_opensearch_client(endpoint: str, region: str, session: boto3.Session | None = None) -> OpenSearch:
    session = session or boto3.Session()
    host = urlparse(endpoint if "//" in endpoint else f"https://{endpoint}").netloc
    return OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=AWSV4SignerAuth(session.get_credentials(), region, "aoss"),  # "aoss" = Serverless
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        pool_maxsize=20,
    )


def index_body(dim: int) -> dict:
    return {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                "embedding": {
                    "type": "knn_vector",
                    "dimension": dim,
                    "method": {"name": "hnsw", "engine": "faiss", "space_type": "l2"},
                },
                "text": {"type": "text"},
                "source": {"type": "keyword"},
                "chunk_index": {"type": "integer"},
            }
        },
    }


def l2_score_to_cosine(score: float) -> float:
    """OpenSearch's faiss/l2 score is 1/(1+d^2). For unit vectors d^2 = 2 - 2cos, so cos = 1 - d^2/2."""
    if score <= 0:
        return 0.0
    d2 = 1.0 / score - 1.0
    return max(-1.0, min(1.0, 1.0 - d2 / 2.0))


class OpenSearchRetriever:
    def __init__(self, client: OpenSearch, embedder: Embedder, index: str):
        self._client, self._embedder, self._index = client, embedder, index

    def retrieve(self, query: str, k: int) -> list[RetrievedChunk]:
        vector = self._embedder.embed(query)
        res = self._client.search(
            index=self._index,
            body={
                "size": k,
                "_source": ["text", "source", "chunk_index"],
                "query": {"knn": {"embedding": {"vector": vector, "k": k}}},
            },
        )
        return [
            RetrievedChunk(
                source=h["_source"]["source"],
                chunk_id=f'{h["_source"]["source"]}#{h["_source"]["chunk_index"]}',
                text=h["_source"]["text"],
                score=l2_score_to_cosine(h["_score"]),
            )
            for h in res["hits"]["hits"]
        ]
