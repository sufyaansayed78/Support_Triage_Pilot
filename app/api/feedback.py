from fastapi import APIRouter, Depends, Query
from botocore.exceptions import ClientError

from app.api.deps import get_container
from app.container import Container
from app.domain import FeedbackIn, FeedbackRecord, TicketStatus
from app.storage.dynamo import DynamoTicketStore

router = APIRouter(tags=["feedback"])

def update_feedback_status(self, ticket_id: str , table : DynamoTicketStore) -> bool:
    try:
            table.update_item(
            Key={"ticket_id": str(ticket_id)},
            UpdateExpression="SET #fs = :submitted",
            ConditionExpression="#fs = :pending",
            ExpressionAttributeNames={
                "#fs": "feedback_status",
            },
            ExpressionAttributeValues={
                ":submitted": TicketStatus.SUBMITTED.value,
                ":pending": TicketStatus.PENDING.value,
            },
        )
        
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    return True
    


@router.post("/v1/tickets/{ticket_id}/feedback", response_model=FeedbackRecord, status_code=201)
def submit_feedback(ticket_id: str, fb: FeedbackIn, c: Container = Depends(get_container)) -> FeedbackRecord:
    return c.feedback.record(ticket_id, fb)


@router.get("/v1/feedback/stats")
def feedback_stats(days: int = Query(7, ge=1, le=90), c: Container = Depends(get_container)) -> dict:
    return c.feedback.stats(days)
