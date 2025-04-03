from ninja import Schema

from registry.api.schema import ErrorMessageResponse

ErrorMessageResponse = ErrorMessageResponse


class TosAccepted(Schema):
    accepted: bool


class TosToSign(Schema):
    text: str
    nonce: str


class TosSigned(Schema):
    tos_type: str
    nonce: str
    signature: str
