from ninja_extra import status
from ninja_extra.exceptions import APIException


class BaseLambdaApiException(APIException):
    pass


class InvalidRequest(BaseLambdaApiException):
    status_code = status.HTTP_400_BAD_REQUEST
