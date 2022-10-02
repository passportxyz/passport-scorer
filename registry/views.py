import json
import logging
from sys import api_version

import didkit
from asgiref.sync import async_to_sync, sync_to_async
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.views import APIView

from registry.models import Passport, Stamp
from registry.serializers import PassportSerializer, StampSerializer

log = logging.getLogger(__name__)


def index(request):
    context = {}
    return render(request, "registry/index.html", context)


async def validate_credential(did, credential):
    # TODO: break this out in an utils module
    stamp_return_errors = []
    credential_subject = credential.get("credentialSubject")
    hash = credential_subject.get("hash")
    stamp_did = credential_subject.get("id").lower()
    provider = credential_subject.get("provider")

    if not credential:
        stamp_return_errors.append("Missing or invalid attribute: credential")

    if not credential_subject:
        stamp_return_errors.append("Missing attribute: credentialSubject")

    if not hash:
        stamp_return_errors.append("Missing attribute: hash")

    if not stamp_did:
        stamp_return_errors.append("Missing attribute: id")

    if not provider:
        stamp_return_errors.append("Missing attribute: provider")

    if did != stamp_did:
        stamp_return_errors.append("Did mismatch")

    verification = await didkit.verify_credential(
        json.dumps(credential), '{"proofPurpose":"assertionMethod"}'
    )
    verification = json.loads(verification)
    print("---- verification", verification)
    if verification["errors"]:
        stamp_return_errors.append(f"Stamp validation failed: {verification['errors']}")

    return stamp_return_errors


# @transaction.atomic
@api_view(["POST"])
def submit_passport(request):
    # TODO: request & verify signature
    # TODO: verify issuer
    errors = []
    stamp_returns = []
    # passport = json.loads(request.body)
    passport = request.data
    log.error("data: %s", passport)
    did = passport.get("did").lower()
    stamps = passport.get("stamps", [])
    status = 200  # TODO: what is the proper status code ??? 204?

    if not did:
        errors.append("Missing attribute: did")

    if not errors:
        passport = Passport.objects.get_or_create(
            did=did, defaults={"passport": passport}
        )[0]
        for stamp in stamps:
            stamp_return_errors = []
            credential = stamp.get("credential")
            stamp_return_errors = async_to_sync(validate_credential)(did, credential)

            credential_subject = credential.get("credentialSubject")
            hash = credential_subject.get("hash")
            provider = credential_subject.get("provider")

            db_stamp = None
            if not stamp_return_errors:
                db_stamp = Stamp.objects.get_or_create(
                    hash=hash,
                    defaults=dict(
                        provider=provider,
                        credential=credential,
                        passport=passport,
                    ),
                )[0]

            stamp_return = {}
            if db_stamp:
                stamp_return["id"] = db_stamp.id
            if stamp_return_errors:
                stamp_return["errors"] = stamp_return_errors

            stamp_returns.append(stamp_return)

    response_data = {"stamps": stamp_returns}

    if errors:
        status = 400
        response_data["errors"] = errors

    return JsonResponse(response_data, status=status)


from rest_framework import viewsets


class PassportViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Passport.objects.all()
    serializer_class = PassportSerializer


class StampViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Stamp.objects.all()
    serializer_class = StampSerializer
