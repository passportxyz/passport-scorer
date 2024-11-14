from decimal import Decimal
from typing import List

from ninja import Schema
from pydantic import field_serializer

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

    @field_serializer("amount")
    def serialize_amount(self, amount: Decimal, _info):
        return format(amount, ".18f")


class GetSchemaResponse(Schema):
    items: List[StakeSchema]
