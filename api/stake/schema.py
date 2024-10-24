from decimal import Decimal
from typing import List

from ninja import Schema

from registry.api.schema import ErrorMessageResponse

ErrorMessageResponse = ErrorMessageResponse


class StakeSchema(Schema):
    chain: int
    staker: str
    stakee: str
    amount: Decimal
    unlock_time: str
    lock_time: str
    last_updated_in_block: int


class GetSchemaResponse(Schema):
    items: List[StakeSchema]
