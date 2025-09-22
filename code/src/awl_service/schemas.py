# src/awl_service/schemas.py
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal

Chain = Literal["btc", "eth"]

class Last20Item(BaseModel):
    # Common fields across BTC/ETH
    block_timestamp: str                      # ISO string
    is_input: Optional[bool] = None           # BTC: True if spending (outgoing). ETH: not used if from/to present
    from_addr: Optional[str] = None
    to_addr: Optional[str] = None
    amount_btc: Optional[float] = None        # BTC amount (if BTC)
    native_value: Optional[float] = None      # ETH native (if ETH)
    token_address: Optional[str] = None
    token_value: Optional[float] = None       # ERC20 value (if ETH)

class ScoreRequest(BaseModel):
    chain: Chain
    last20: List[Last20Item] = Field(default_factory=list)
    approvals: Optional[int] = 0              # ETH-only extra signal (can be 0/None for BTC)

    @field_validator("last20")
    @classmethod
    def limit_last20(cls, v):
        return v[:20] if len(v) > 20 else v

class ScoreResponse(BaseModel):
    chain: Chain
    risk: int
    flag: bool
    reasons: List[str]
    features: dict
