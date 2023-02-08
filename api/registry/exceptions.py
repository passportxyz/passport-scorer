from ninja_extra import status
from ninja_extra.exceptions import APIException


class InvalidSignerException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Address does not match signature."


class InvalidNonceException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid nonce."


class InvalidPassportCreationException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Error Creating Passport."


class InvalidScoreRequestException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to get score for provided community."


class NoPassportException(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "No Passport found for this address."


class Unauthorized(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid API Key."


class InvalidCommunityScoreRequestException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to get score for provided community."


class InvalidLimitException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid limit."


class NoRequiredPermissionsException(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You are not allowed to access this endpoint."


class InternalServerErrorException(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Internal Server Error."
