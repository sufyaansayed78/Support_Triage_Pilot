import json
from datetime import datetime
from decimal import Decimal

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from app.domain import (Category, Decision, FeedbackAction, FeedbackRecord, Ticket, TicketRecord, TicketStatus,
                        TriageResult)


def to_item(model_dict: dict) -> dict:
    """JSON round-trip turns floats into Decimal, which DynamoDB requires."""
    return json.loads(json.dumps(model_dict, default=str), parse_float=Decimal)


def from_item(item: dict) -> dict:
    return json.loads(json.dumps(item, default=lambda o: float(o) if isinstance(o, Decimal) else str(o)))


def _to_record(item: dict) -> TicketRecord:
    data = from_item(item)
    triage = data.pop("triage", None)
    ticket = Ticket(**{k: v for k, v in data.items() if k in Ticket.model_fields})
    return TicketRecord(ticket=ticket, result=TriageResult(**triage) if triage else None)


class DynamoTicketStore:
    """Table: pk=ticket_id. GSI `decision-index` (pk=decision, sk=created_at) powers the queue endpoints."""

    def __init__(self, table, decision_index: str = "decision-index"):
        self._table, self._decision_index = table, decision_index

    def save_ticket(self, ticket: Ticket) -> None:
        self._table.put_item(Item=to_item(ticket.model_dump(mode="json")))

    def save_result(self, result: TriageResult) -> None:
        self._table.update_item(
            Key={"ticket_id": str(result.ticket_id)},
            UpdateExpression="SET #t = :t, #c = :c, #d = :d",
            ExpressionAttributeNames={"#t": "triage", "#c": "category", "#d": "decision"},
            ExpressionAttributeValues={
                ":t": to_item(result.model_dump(mode="json")),
                ":c": result.category.value,
                ":d": result.decision.value,
            },
        )

    def get(self, ticket_id: str) -> TicketRecord | None:
        item = self._table.get_item(Key={"ticket_id": ticket_id}).get("Item")
        return _to_record(item) if item else None

    def get_all(self) -> list[TicketRecord]:
        records: list[TicketRecord] = []
        kwargs: dict = {}
        while True:  
            page = self._table.scan(**kwargs)
            records.extend(_to_record(i) for i in page.get("Items", []))
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        return sorted(records, key=lambda r: r.ticket.created_at, reverse=True)

    def list_by_decisions(self, decisions: list[Decision], pending_only: bool = True) -> list[TicketRecord]:
        records: list[TicketRecord] = []
        for decision in decisions:
            kwargs: dict = dict(
                IndexName=self._decision_index,
                KeyConditionExpression=Key("decision").eq(decision.value),
                ScanIndexForward=False,  # newest first
            )
            if pending_only:
                kwargs["FilterExpression"] = Attr("feedback_status").eq(TicketStatus.PENDING.value) | Attr("feedback_status").not_exists()
            while True:
                page = self._table.query(**kwargs)
                records.extend(_to_record(i) for i in page.get("Items", []))
                if "LastEvaluatedKey" not in page:
                    break
                kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        return sorted(records, key=lambda r: r.ticket.created_at, reverse=True)

    def mark_feedback_submitted(self, ticket_id: str) -> bool:
        try:
            self._table.update_item(
                Key={"ticket_id": str(ticket_id)},
                UpdateExpression="SET #fs = :submitted",
                ConditionExpression="attribute_not_exists(#fs) OR #fs = :pending",
                ExpressionAttributeNames={"#fs": "feedback_status"},
                ExpressionAttributeValues={":submitted": TicketStatus.SUBMITTED.value, ":pending": TicketStatus.PENDING.value},
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise


class DynamoFeedbackStore:
    """Table: pk=ticket_id, sk=feedback_id. GSI (category, created_at) powers the stats endpoint."""

    def __init__(self, table, category_index: str):
        self._table, self._index = table, category_index

    def save(self, record: FeedbackRecord) -> None:
        item = record.model_dump(mode="json")
        item = {k: v for k, v in item.items() if v is not None}
        self._table.put_item(Item=to_item(item))

    def counts_since(self, since: datetime) -> dict[Category, dict[FeedbackAction, int]]:
        out: dict[Category, dict[FeedbackAction, int]] = {}
        for cat in Category:
            counts = {a: 0 for a in FeedbackAction}
            kwargs = dict(
                IndexName=self._index,
                KeyConditionExpression=Key("category").eq(cat.value) & Key("created_at").gte(since.isoformat()),
                ProjectionExpression="#a",
                ExpressionAttributeNames={"#a": "action"},
            )
            while True:
                page = self._table.query(**kwargs)
                for item in page["Items"]:
                    counts[FeedbackAction(item["action"])] += 1
                if "LastEvaluatedKey" not in page:
                    break
                kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
            if any(counts.values()):
                out[cat] = counts
        return out
