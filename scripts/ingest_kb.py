#!/usr/bin/env python3
"""Build the OpenSearch Serverless vector index from knowledge-base docs stored in S3.

    python -m scripts.ingest_kb                       # uses TRIAGE_* env vars
    python -m scripts.ingest_kb --prefix kb/ --recreate

Idempotent per document: existing chunks for a source are deleted before re-indexing
(OpenSearch Serverless vector collections do not support client-supplied document IDs).
"""
import argparse
from concurrent.futures import ThreadPoolExecutor

import boto3
from opensearchpy import helpers

from app.config import get_settings
from app.generation.embeddings import BedrockEmbedder
from app.generation.retriever_opensearch import index_body, make_opensearch_client
from app.kb.chunking import chunk_markdown


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default=None, help="S3 key prefix (default: TRIAGE_KB_PREFIX)")
    ap.add_argument("--recreate", action="store_true", help="drop and recreate the index first")
    args = ap.parse_args()

    s = get_settings()
    prefix = args.prefix or s.kb_prefix
    session = boto3.Session(region_name=s.aws_region)
    s3, bedrock = session.client("s3"), session.client("bedrock-runtime")
    os_client = make_opensearch_client(s.opensearch_endpoint, s.aws_region, session)
    embedder = BedrockEmbedder(bedrock, s.embedding_model_id, s.embedding_dim)

    if args.recreate and os_client.indices.exists(index=s.opensearch_index):
        os_client.indices.delete(index=s.opensearch_index)
    if not os_client.indices.exists(index=s.opensearch_index):
        os_client.indices.create(index=s.opensearch_index, body=index_body(s.embedding_dim))

    keys = [
        o["Key"]
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=s.kb_bucket, Prefix=prefix)
        for o in page.get("Contents", [])
        if o["Key"].endswith((".md", ".txt"))
    ]
    print(f"found {len(keys)} documents under s3://{s.kb_bucket}/{prefix}")

    total = 0
    for key in keys:
        text = s3.get_object(Bucket=s.kb_bucket, Key=key)["Body"].read().decode("utf-8")
        chunks = chunk_markdown(text)
        with ThreadPoolExecutor(max_workers=8) as pool:
            vectors = list(pool.map(embedder.embed, chunks))

        os_client.delete_by_query(index=s.opensearch_index, body={"query": {"term": {"source": key}}}, params={"conflicts": "proceed"})
        helpers.bulk(
            os_client,
            ({"_index": s.opensearch_index,
              "_source": {"text": c, "embedding": v, "source": key, "chunk_index": i}}
             for i, (c, v) in enumerate(zip(chunks, vectors))),
        )
        total += len(chunks)
        print(f"  indexed {key}: {len(chunks)} chunks")
    print(f"done: {total} chunks")


if __name__ == "__main__":
    main()
