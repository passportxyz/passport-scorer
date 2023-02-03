from ninja_extra.exceptions import APIException
from ninja_extra import status


class InvalidDeleteCacheRequestException(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Unable to find stamp to delete."


class InvalidSessionException(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = (
        "You are unable to modify a stamp that is not associated with your session"
    )
