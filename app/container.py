"""Composition root: the only module that knows which concrete implementations are wired in."""
from dataclasses import dataclass

from app.classification.heuristic import HeuristicClassifier
from app.config import Settings
from app.feedback.service import FeedbackService
from app.generation.local import LocalRetriever, TemplateGenerator
from app.generation.base import Embedder
from app.ingestion.service import IngestionService
from app.observability.metrics import EmfMetrics, NullMetrics
from app.routing.policy import RoutingPolicy
from app.storage.base import TicketStore
from app.storage.memory import MemoryFeedbackStore, MemoryTicketStore
from app.triage.service import TriageService


@dataclass
class Container:
    settings: Settings
    policy: RoutingPolicy
    tickets: TicketStore
    ingestion: IngestionService
    triage: TriageService
    feedback: FeedbackService
    embedder: Embedder | None = None  # only set on the aws backend


def build_container(s: Settings) -> Container:
    policy = RoutingPolicy(s.acceptance_threshold, s.min_grounding_score)

    if s.backend == "local":
        tickets, feedback_store, embedder = MemoryTicketStore(), MemoryFeedbackStore(), None
        classifier, retriever, generator = HeuristicClassifier(), LocalRetriever(s.local_kb_dir), TemplateGenerator()
        metrics = NullMetrics()
    else:
        import boto3
        from botocore.config import Config

        from app.classification.bedrock import BedrockClassifier
        from app.generation.bedrock import BedrockGenerator
        from app.generation.embeddings import BedrockEmbedder
        from app.generation.retriever_opensearch import OpenSearchRetriever, make_opensearch_client
        from app.storage.dynamo import DynamoFeedbackStore, DynamoTicketStore

        session = boto3.Session(region_name=s.aws_region)
        cfg = Config(retries={"max_attempts": 3, "mode": "standard"}, read_timeout=30, connect_timeout=5)
        bedrock = session.client("bedrock-runtime", config=cfg)
        ddb = session.resource("dynamodb", config=cfg)

        tickets = DynamoTicketStore(ddb.Table(s.tickets_table), s.tickets_decision_index)
        feedback_store = DynamoFeedbackStore(ddb.Table(s.feedback_table), s.feedback_category_index)
        classifier = BedrockClassifier(bedrock, s.llm_model_id)
        generator = BedrockGenerator(bedrock, s.llm_model_id)
        embedder = BedrockEmbedder(bedrock, s.embedding_model_id, s.embedding_dim)
        retriever = OpenSearchRetriever(make_opensearch_client(s.opensearch_endpoint, s.aws_region, session), embedder, s.opensearch_index)
        metrics = EmfMetrics(s.metrics_namespace)

    return Container(
        settings=s, policy=policy, tickets=tickets,
        ingestion=IngestionService(tickets),
        triage=TriageService(classifier, retriever, generator, policy, tickets, metrics, s.rag_top_k),
        feedback=FeedbackService(tickets, feedback_store, metrics),
        embedder=embedder,
    )
