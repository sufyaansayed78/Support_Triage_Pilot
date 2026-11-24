from concurrent.futures import ThreadPoolExecutor
from app.api.deps import get_container
from app.container import Container
from opensearchpy import helpers
from starlette.concurrency import run_in_threadpool
import boto3
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from app.config import Settings, get_settings
from app.generation.embeddings import BedrockEmbedder
from app.generation.retriever_opensearch import index_body, make_opensearch_client
from app.kb.chunking import chunk_markdown
import fitz
from app.generation.base import Embedder
s3_client = boto3.client("s3")

router = APIRouter(prefix="/v1/ingestion", tags=["tickets"])

def upload_pdf_to_s3(file: UploadFile, bucket_name : str ) :
    try:
        # Generate a unique S3 object key
        file_key = f"kb/{file.filename}.pdf"

        # Upload directly from the file stream
        s3_client.upload_fileobj(
            file.file,
            bucket_name,
            file_key,
            ExtraArgs={
                "ContentType": "application/pdf"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload PDF to S3: {str(e)}"
        )
        
def embed_doc(text:str , filename : str ):
        s = get_settings()
        session = boto3.Session(region_name=s.aws_region)
        s3, bedrock = session.client("s3"), session.client("bedrock-runtime")
        os_client = make_opensearch_client(s.opensearch_endpoint, s.aws_region, session)
        embedder = BedrockEmbedder(bedrock, s.embedding_model_id, s.embedding_dim)
        chunks = chunk_markdown(text)
        with ThreadPoolExecutor(max_workers=8) as pool:
            vectors = list(pool.map(embedder.embed, chunks))

        if not os_client.indices.exists(index=s.opensearch_index):
                os_client.indices.create(index=s.opensearch_index, body=index_body(s.embedding_dim))

        os_client.delete_by_query(index=s.opensearch_index, body={"query": {"term": {"source": filename}}}, params={"conflicts": "proceed"})
        helpers.bulk(
            os_client,
            ({"_index": s.opensearch_index,
                "_source": {"text": c, "embedding": v, "source": filename, "chunk_index": i}}
                for i, (c, v) in enumerate(zip(chunks, vectors))),
        )
        







@router.post("/pdf", status_code=201)
async def ingest_doc(
    file: UploadFile = File(...),
    c: Container = Depends(get_container)
):

    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    try:
        pdf_bytes = await file.read()

        if not pdf_bytes.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail="Invalid PDF file"
            )

        document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        try:
            extracted_text = [
                page.get_text()
                for page in document
            ]
            total_pages = len(document)
        finally:
            document.close()

        full_text = "\n".join(extracted_text)

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"PDF extraction failed: {str(exc)}"
        )

    # Reset file pointer before uploading to S3
    try:
        await file.seek(0)

        s3_key = await run_in_threadpool(
            upload_pdf_to_s3,
            file,
            c.settings.kb_bucket
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"S3 upload failed: {str(exc)}"
        )

    try:
        result = await run_in_threadpool(
            embed_doc,
            full_text,
            file.filename,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"PDF ingestion failed: {str(exc)}"
        )

    return {
        "filename": file.filename,
        "total_pages": total_pages,
        "s3_key": s3_key,
        "message": "PDF uploaded and ingested successfully"
    }
