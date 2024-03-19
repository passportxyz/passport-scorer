from ninja import Schema
from registry.api.schema import ErrorMessageResponse

ErrorMessageResponse = ErrorMessageResponse


class StakeSchema(Schema):
    chain: int
    staker: str
    stakee: str
    amount: str
    unlock_time: str
    lock_time: str
