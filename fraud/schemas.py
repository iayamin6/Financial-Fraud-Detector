from datetime import datetime,timezone
from typing import Literal,Any
from pydantic import BaseModel,Field,ConfigDict,field_validator

class Transaction(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    transaction_id: str=Field(min_length=1,max_length=128,pattern=r'^[A-Za-z0-9_.:-]+$')
    sender_id: str=Field(min_length=1,max_length=128)
    recipient_id: str=Field(min_length=1,max_length=128)
    amount: float=Field(gt=0,le=1e12)
    timestamp: datetime
    account_age_days: int=Field(ge=0,le=50000)
    device_id: str|None=Field(default=None,max_length=128)
    ip_address: str|None=Field(default=None,max_length=128)
    relationship_group: str|None=Field(default=None,max_length=128)
    country: str|None=Field(default=None,min_length=2,max_length=3)
    text: str|None=Field(default=None,max_length=5000)

    @field_validator('timestamp')
    @classmethod
    def utc_timestamp(cls,value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Timestamp must include a UTC offset')
        return value.astimezone(timezone.utc)

class BatchRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    transactions: list[Transaction]=Field(min_length=1,max_length=10000)

class Feedback(BaseModel):
    model_config=ConfigDict(extra='forbid')
    transaction_id: str=Field(min_length=1,max_length=128)
    correct_label: Literal[0,1]
    comment: str|None=Field(default=None,max_length=2000)

class ScoreResponse(BaseModel):
    transaction_id: str
    fraud_score: float=Field(ge=0,le=1)
    risk_tier: Literal['low','medium','high']
    decision: Literal['auto_pass','manual_review','auto_block']
    sub_scores: dict[str,float]
    reasons: list[str]
    layers: dict[str,Any]
    fusion: dict[str,Any]
    latency_ms: dict[str,float]
    model_version: str
    scored_at: datetime
    component_versions: dict[str,str]=Field(default_factory=dict)
    aml_review_required: bool=False

class FeedbackResponse(BaseModel):
    transaction_id: str
    correct_label: Literal[0,1]
    classification: Literal['false_positive','false_negative','confirmed_fraud','confirmed_legitimate']

class ExplanationResponse(BaseModel):
    transaction_id: str
    model_version: str
    methods: dict[str,Any]
    reasons: list[str]

class HealthResponse(BaseModel):
    status: Literal['ready']
    model_version: str

class MetricsResponse(BaseModel):
    scored_transactions: int=Field(ge=0)
    average_latency_ms: dict[str,float]
    scope: str
    model_version: str

class PolicyResponse(BaseModel):
    weights: dict[str,float]
    review_threshold: float=Field(ge=0,le=1)
    block_threshold: float=Field(ge=0,le=1)
    hard_rule_floor: float=Field(ge=0,le=1)
