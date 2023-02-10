from ninja_extra import status
from ninja_extra.exceptions import APIException


class InvalidDeleteCacheRequestException(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Unable to find stamp to delete."


class InvalidSessionException(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = (
        "You are unable to modify a stamp that is not associated with your session"
    )


class TooManyStampsException(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "You have submitted too many stamps."
