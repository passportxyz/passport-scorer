from typing import List

from ceramic_cache.api import JWTDidAuth
from django.db.models import Subquery
from ninja import Router, Schema

from .models import DismissedBanners, PassportBanner

router = Router()


def get_address(did: str):
    start = did.index("0x")
    return did[start:]


class Banner(Schema):
    content: str
    link: str
    banner_id: int


@router.get(
    "/banners",
    response=List[Banner],
    auth=JWTDidAuth(),
)
def get_banners(request):
    """
    Get all banners
    """
    try:
        address = get_address(request.auth.did)
        banners = (
            PassportBanner.objects.filter(is_active=True)
            .exclude(
                pk__in=Subquery(
                    DismissedBanners.objects.filter(address=address).values("banner_id")
                )
            )
            .all()
        )

        return [Banner(content=b.content, link=b.link, banner_id=b.pk) for b in banners]
    except:
        return {
            "status": "failed",
        }


class GenericResponse(Schema):
    status: str


@router.post(
    "/banners/{banner_id}/dismiss",
    response={200: GenericResponse},
    auth=JWTDidAuth(),
)
def dismiss_banner(request, banner_id: int):
    """
    Dismiss a banner
    """
    try:
        banner = PassportBanner.objects.get(id=banner_id)
        address = get_address(request.auth.did)
        DismissedBanners.objects.create(address=address, banner=banner)
        return {
            "status": "success",
        }
    except PassportBanner.DoesNotExist:
        return {
            "status": "failed",
        }
