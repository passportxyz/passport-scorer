from ninja import Schema
from typing import List
from registry.api.schema import ErrorMessageResponse

ErrorMessageResponse = ErrorMessageResponse


class StakeSchema(Schema):
    chain: int
    staker: str
    stakee: str
    amount: str
    unlock_time: str
    lock_time: str
    last_updated_in_block: str


class GetSchemaResponse(Schema):
    items: List[StakeSchema]
