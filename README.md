# Customer Support Triage Co-pilot

FastAPI microservice that triages inbound support tickets, drafts grounded replies for human agents, and learns from their accept / edit / reject feedback.
**Stack:** Python 3.12, FastAPI, React + Vite (web UI), Amazon Bedrock, ECS Fargate + ALB, OpenSearch Serverless, DynamoDB, S3, CloudWatch, AWS CDK.

```
                         POST /v1/tickets
  client ──► ALB ──► ECS Fargate (FastAPI)
                       │
        ┌──────────────┼────────────────────────────────────────────┐
        │ 1 ingestion  │ 2 classification   3 routing policy   4 generation
        │ validate,    │ Bedrock LLM ──►    safety net + never-    OpenSearch kNN ──► Bedrock LLM
        │ normalise,   │ (category,         auto list + threshold  (RAG over S3 KB)    (grounded draft
        │ persist      │  confidence)       = ESCALATE / TRIAGE /                      or NO_ANSWER)
        └──────┬───────┴────────────────────  DRAFT_READY ─────────────────────────────┘
               ▼
          DynamoDB (tickets)          POST /v1/tickets/{id}/feedback ──► DynamoDB (feedback)
                                                      │
          stdout EMF logs ──► CloudWatch Metrics ◄────┘──► drift dashboard + alarm
          S3 (KB docs) ──► scripts/ingest_kb.py ──► OpenSearch Serverless vector index
```

## Layout
| Path | Responsibility |
|---|---|
| `app/ingestion` | Validate / normalise / persist tickets. No model or routing knowledge. |
| `app/classification` | `Classifier` protocol; Bedrock implementation with defensive JSON parsing; keyword baseline for local mode. |
| `app/routing/policy.py` | **All routing decisions.** Hard-coded `NEVER_AUTO_RESPOND` (5 categories), regex safety net, tunable threshold, grounding floor. |
| `app/generation` | Embeddings, OpenSearch kNN retriever, Bedrock generator (answers only from retrieved context, else `NO_ANSWER`). |
| `app/triage` | Thin orchestrator: classify → route → retrieve → generate. |
| `app/feedback` | Persists accept/edit/reject, computes edit ratio, emits metrics, serves `/v1/feedback/stats`. |
| `app/storage` | DynamoDB and in-memory implementations behind protocols. |
| `app/observability` | CloudWatch Embedded Metric Format emitter. |
| `app/container.py` | Composition root (the only place that picks `aws` vs `local`). |
| `frontend/` | React + Vite web UI: create a ticket, browse the three ticket lists, send accept / edit / reject feedback, view feedback stats. Compiled into the Docker image and served by FastAPI. |
| `infra/` | CDK stack: VPC, ALB + Fargate service, DynamoDB, S3, AOSS collection + policies, dashboard, alarm. |
| `scripts/ingest_kb.py` | S3 → chunk → Titan embeddings → OpenSearch index. |

## Routing logic
1. Classifier proposes `(category, confidence)`.
2. **Safety net:** regexes for the five sensitive areas override the model if it said anything else (defends against misclassification and prompt injection).
3. **Never-auto-respond** categories (`legal_threat`, `security_incident`, `payment_dispute`, `privacy_request`, `safety_or_harassment`) → `escalate`, regardless of confidence. No retrieval, no draft.
4. `other`, or confidence `< TRIAGE_ACCEPTANCE_THRESHOLD` → `human_triage`, no draft.
5. Retrieve top-k chunks. If the best cosine similarity `< TRIAGE_MIN_GROUNDING_SCORE`, or the generator returns `NO_ANSWER` → `human_triage`.
6. Otherwise → `draft_ready`, with citations.

Humans always make the final send decision; the "acceptance" in the threshold is whether the system offers a draft.

## Run locally (no AWS needed)
```bash
make install
make test
make run                       # TRIAGE_BACKEND=local: in-memory stores, keyword classifier, ./kb retrieval
curl -s localhost:8000/v1/tickets -H 'content-type: application/json' \
  -d '{"subject":"Locked out","body":"I forgot my password, how do I reset it?"}'
curl -s localhost:8000/v1/tickets/<ticket_id>/feedback -H 'content-type: application/json' -d '{"action":"accept"}'
curl -s 'localhost:8000/v1/feedback/stats?days=7'
```
Docs at `http://localhost:8000/docs`.

## Web UI (React + Vite)
Three screens, all talking to the endpoints below:

| Screen | What it does | Endpoints |
|---|---|---|
| **New ticket** | Create a ticket and see the triage result: decision, confidence vs threshold, reasons, draft, sources. One-click example tickets cover all three outcomes. | `POST /v1/tickets` |
| **Queue** | Three tabs, one per list endpoint, with search. Open a ticket to read it and send feedback (accept / edit / reject, optional agent ID and reason). | `GET /v1/tickets`, `GET /v1/tickets/AI_drafted_tickets`, `GET /v1/tickets/Escalated_tickets`, `GET /v1/tickets/{id}`, `POST /v1/tickets/{id}/feedback` |
| **Insights** | Accept / edit / reject split overall and by category, plus the live routing policy. | `GET /v1/feedback/stats?days=`, `GET /v1/policy` |

`AI_drafted_tickets` = drafts nobody has reviewed yet. `Escalated_tickets` = escalated or human-triage tickets with no feedback yet. Sending feedback flips `feedback_status` to `Submitted`, which removes the ticket from both lists (it stays in "All tickets").

**Develop** (hot reload; Vite proxies `/v1` to the API, so no CORS setup):
```bash
make install && make ui-install
make dev            # API on :8000 + UI on :5173
```
**Run as one container** (API + compiled UI on one origin):
```bash
docker compose up --build        # http://localhost:8000  (API docs at /docs)
```
The Dockerfile is multi-stage: Node builds `frontend/` and the result is copied into `app/static`, which FastAPI serves at `/`. The ECS task, ALB target group and health check (`/healthz`) are unchanged: the same single container now serves both the UI and the API.

## Deploy to AWS
```bash
cd infra && pip install -r requirements.txt
cdk bootstrap && cdk deploy -c ingest_principal_arn=<your IAM role/user ARN>   # needs Docker running

# load the knowledge base
aws s3 sync ../kb s3://<KbBucketName>/kb/
export TRIAGE_BACKEND=aws TRIAGE_OPENSEARCH_ENDPOINT=<CollectionEndpoint> TRIAGE_KB_BUCKET=<KbBucketName> TRIAGE_AWS_REGION=eu-west-1
(cd .. && python -m scripts.ingest_kb)
```
Prerequisites: enable model access in Bedrock for the models in `TRIAGE_LLM_MODEL_ID` / `TRIAGE_EMBEDDING_MODEL_ID` in your region (change the IDs if you prefer other models; if your region needs cross-region inference profiles, use the profile ID).
Tune the threshold with `TRIAGE_ACCEPTANCE_THRESHOLD` in `infra/stack.py` and redeploy (rolling, with circuit-breaker rollback).

## Feedback loop and drift
Each feedback event is stored in DynamoDB (`ticket_id`, `feedback_id`, category, confidence, action, edit ratio, agent, reason) and emits EMF metrics: `FeedbackAccept/Edit/Reject` (always 0/1 so metric math has no gaps), `EditRatio`, plus triage-time `Decision*` and `Confidence`, each under `Category` and an all-category rollup. The `support-triage-drift` dashboard plots daily acceptance rate (overall and per category), feedback volume, routing mix, mean confidence and edit ratio. An alarm fires if the daily acceptance rate is below 60% for 3 days (ignoring days with fewer than 20 reviews).
Use the stored accept/edit/reject data to re-tune the threshold per category or build an eval set.

## Known limitations / next steps
- LLM-reported confidence is not calibrated. Use accumulated feedback to calibrate (e.g. isotonic regression per category) or add a logit-based/ensemble score.
- Triage runs synchronously in the request. For high volume, put SQS between ingestion and triage.
- The ALB listener is HTTP; add an ACM certificate + HTTPS listener and auth (e.g. API Gateway/JWT or Cognito) before exposing it.
- `/v1/feedback/stats` queries the DynamoDB GSI per category; fine at moderate volume, use CloudWatch or Athena beyond that.
- `app/classification/Anthropic.py` and `app/api/Ingestion.py` (PDF upload) are not wired into the app yet and need fixes first.
- The ticket list endpoints use a DynamoDB Scan / GSI query with no API pagination; add `limit` + cursor before the table grows.
- The safety net is intentionally broad (e.g. "refund" escalates), so expect some over-escalation.
