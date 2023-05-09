from django.shortcuts import _get_queryset
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
    default_detail = "Unable to get score for provided scorer."


class NoPassportException(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "No Passport found for this address."


class Unauthorized(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Invalid API Key."


class InvalidCommunityScoreRequestException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to get score for provided scorer."


class InvalidScorerIdException(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Invalid scorer_id. Please provide a valid scorer_id."


class InvalidLimitException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid limit."


class NoRequiredPermissionsException(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You are not allowed to access this endpoint."


class InternalServerErrorException(APIException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "Internal Server Error."


class NotFoundApiException(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Not found."


class InvalidAPIKeyPermissions(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Invalid permissions for creating scorer"


def api_get_object_or_404(klass, *args, **kwargs):
    """
    Note: this is an adjusted clone of djangos get_object_or_404
    ------
    Use get() to return an object, or raise an Http404 exception if the object
    does not exist.

    klass may be a Model, Manager, or QuerySet object. All other passed
    arguments and keyword arguments are used in the get() query.

    Like with QuerySet.get(), MultipleObjectsReturned is raised if more than
    one object is found.
    """
    queryset = _get_queryset(klass)
    if not hasattr(queryset, "get"):
        klass__name = (
            klass.__name__ if isinstance(klass, type) else klass.__class__.__name__
        )
        raise ValueError(
            f"First argument to get_object_or_404() must be a Model, Manager, or QuerySet, not '{klass__name}'."
        )
    try:
        return queryset.get(*args, **kwargs)
    except queryset.model.DoesNotExist as exc:
        raise NotFoundApiException(
            f"No {queryset.model._meta.object_name} matches the given query."
        ) from exc
