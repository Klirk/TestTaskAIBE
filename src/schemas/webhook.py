from pydantic import BaseModel, ConfigDict, Field


class HelpdeskWebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    event_id: str = Field(min_length=1, max_length=128)
    ticket_id: str = Field(min_length=1, max_length=128)
    customer_email: str = Field(min_length=3, max_length=255)
    message: str = Field(min_length=1)
    reply_url: str = Field(min_length=1, max_length=1024)


class WebhookAckResponse(BaseModel):
    status: str
    event_id: str
    ticket_id: str
    duplicate: bool
