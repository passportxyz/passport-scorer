import json
import logging
from datetime import datetime

import didkit
from asgiref.sync import async_to_sync
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from eth_account.messages import encode_defunct
from reader.passport_reader import TRUSTED_IAM_ISSUER
from registry.models import Passport, Stamp

# from registry.serializers import PassportSerializer, StampSerializer
from registry.signals import registry_updated

# from rest_framework import viewsets
# from rest_framework.decorators import api_view
from web3 import Web3

log = logging.getLogger(__name__)

web3 = Web3()


def index(request):
    context = {}
    return render(request, "registry/index.html", context)


async def validate_credential(did, credential):
    # pylint: disable=fixme
    # TODO: break this out in an utils module
    stamp_return_errors = []
    credential_subject = credential.get("credentialSubject")
    stamp_hash = credential_subject.get("hash")
    stamp_did = credential_subject.get("id").lower()
    provider = credential_subject.get("provider")

    if not credential:
        stamp_return_errors.append("Missing or invalid attribute: credential")

    if not credential_subject:
        stamp_return_errors.append("Missing attribute: credentialSubject")

    if not stamp_hash:
        stamp_return_errors.append("Missing attribute: hash")

    if not stamp_did:
        stamp_return_errors.append("Missing attribute: id")

    if not provider:
        stamp_return_errors.append("Missing attribute: provider")

    if did != stamp_did:
        stamp_return_errors.append("Did mismatch")

    # pylint: disable=no-member
    verification = await didkit.verify_credential(
        json.dumps(credential), '{"proofPurpose":"assertionMethod"}'
    )
    verification = json.loads(verification)

    if verification["errors"]:
        stamp_return_errors.append(f"Stamp validation failed: {verification['errors']}")

    return stamp_return_errors


def get_duplicate_passport(did, stamp_hash):
    stamps = Stamp.objects.filter(hash=stamp_hash).exclude(passport__did=did)
    if stamps.exists():
        log.debug(
            "Duplicate did '%s' for stamp '%s'", stamps[0].passport.did, stamp_hash
        )
        return stamps[0].passport

    return None


def get_signing_message(nonce: str) -> str:
    return f"""I hereby agree to submit my address in order to score my associated Gitcoin Passport from Ceramic.

Nonce: {nonce}
"""


def get_signer(nonce: str, signature: str) -> str:
    message = get_signing_message(nonce)
    encoded_message = encode_defunct(text=message)
    address = web3.eth.account.recover_message(encoded_message, signature=signature)
    return address


def verify_issuer(stamp: dict) -> bool:
    return (
        "credential" in stamp
        and "issuer" in stamp["credential"]
        and stamp["credential"]["issuer"] == TRUSTED_IAM_ISSUER
    )


def verify_expiration(passport) -> bool:
    format = "%Y-%m-%dT%H:%M:%S.%fZ"
    stamps = passport["stamps"]
    for index in stamps:
        if (
            datetime.strptime(index["credential"]["expirationDate"], format)
            < datetime.now()
        ):
            return False
    return True


def submit_passport(request):
    # pylint: disable=fixme
    # TODO: verify expiration date
    errors = []
    stamp_returns = []
    # passport = json.loads(request.body)
    passport = request.data
    log.error("data: %s", passport)
    did = passport.get("did").lower()
    stamps = passport.get("stamps", [])
    # pylint: disable=fixme
    status = 200  # TODO: what is the proper status code ??? 204?

    if not did:
        errors.append("Missing attribute: did")

    sorted_passports = Passport.objects.order_by("-version")
    if sorted_passports.exists():
        last_version = sorted_passports[0].version
    else:
        last_version = 0

    new_version = last_version + 1
    passports_to_update = {}
    if not errors:
        db_passport = Passport.objects.get_or_create(
            did=did, defaults={"passport": passport, "version": new_version}
        )[0]

        # Variable to record all passports affected by this submission. This
        # will also passports that have duplicate stamps removed as part of de-duping
        passports_to_update[db_passport.id] = db_passport

        for stamp in stamps:

            stamp_return_errors = []
            credential = stamp.get("credential")
            stamp_return_errors = async_to_sync(validate_credential)(did, credential)

            credential_subject = credential.get("credentialSubject")
            stamp_hash = credential_subject.get("hash")

            duplicate_passport = get_duplicate_passport(did, stamp_hash)
            if duplicate_passport:
                passports_to_update[duplicate_passport.id] = duplicate_passport

            db_stamp = None
            if not stamp_return_errors:
                # This will create the stamp or update the previous stamp, and link it to the
                # the current passport if it is the case.
                log.debug("Saving stamp '%s' to passport '%s'", stamp_hash, db_passport)
                db_stamp = Stamp.objects.update_or_create(
                    hash=stamp_hash,
                    defaults=dict(
                        provider=credential_subject.get("provider"),
                        credential=credential,
                        passport=db_passport,
                    ),
                )[0]

            stamp_return = {}
            if db_stamp:
                stamp_return["id"] = db_stamp.id

            if stamp_return_errors:
                stamp_return["errors"] = stamp_return_errors

            stamp_returns.append(stamp_return)

        if passports_to_update:
            passport_list = []
            for passport_to_update in passports_to_update.values():
                passport_to_update.version = new_version
                passport_list.append(passport_to_update)

            Passport.objects.bulk_update(passport_list, ["version"])

    response_data = {"stamps": stamp_returns}

    if errors:
        log.debug("errors occured, not sending signal. Errors %s", errors)
        status = 400
        response_data["errors"] = errors
    else:
        affected_passports = list(passports_to_update.keys())
        log.debug("sending registry_updated signal for %s", affected_passports)
        registry_updated.send(Passport, passport_ids=affected_passports)
        response_data["affected_passports"] = affected_passports

    return JsonResponse(response_data, status=status)
