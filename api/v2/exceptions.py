from ninja_extra import status
from ninja_extra.exceptions import APIException


class ScoreDoesNotExist(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "No score exists."

    def __init__(self, address: str, *args, **kwargs):
        self.address = address
        super().__init__(*args, **kwargs)
