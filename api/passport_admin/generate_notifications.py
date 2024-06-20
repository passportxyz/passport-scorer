# import dag_cbor
# import hashlib

# from django.utils import timezone
# from registry.models import Event
# from registry.models import Passport, Stamp
# from ceramic_cache.models import CeramicCache
# from passport_admin.models import Notification


# def generate_deduplication_notifications(address):
#     """
#     Generate deduplication notifications for a specific address
#     """
#     deduplication_events = Event.objects.filter(
#         address=address, action=Event.Action.LIFO_DEDUPLICATION
#     ).all()

#     if len(deduplication_events) > 0:
#         # for each deduplication event, generate a notification
#         # if the notification does not already exist
#         for event in deduplication_events:
#             # Crate a hash for the notification id  using https://docs.python.org/3/library/hashlib.html
#             encoded_data = dag_cbor.encode(
#                 {
#                     "action": event.action,
#                     "address": event.address,
#                     "community": event.community,
#                     "data": event.data,
#                     "created_at": event.created_at,
#                     "id": event.id,
#                 }
#             )

#             notification_id = hashlib.sha256(encoded_data).hexdigest()
#             notification_exists = Notification.objects.filter(
#                 notification_id=notification_id
#             ).exists()

#             stamp_name = event.data.get("provider", "<StampName>")
#             if not notification_exists:
#                 Notification.objects.create(
#                     notification_id=notification_id,
#                     type="deduplication",
#                     is_active=True,
#                     title=f"'{stamp_name}' Duplicate Stamp Claim",
#                     content=f"You have claimed the same '{stamp_name}' stamp in two Passports. We only count your stamp once. This duplicate is in your wallet {address}. Learn more about deduplication <a href='https://github.com/orgs/gitcoinco/projects/6/views/link'>here</a>",
#                     created_at=timezone.now().date(),
#                     eth_address=address,
#                 )


# def generate_stamp_expired_notifications(address):
#     """
#     Generate stamp expired notifications for a specific address
#     """
#     current_date = timezone.now().date()

#     # Get CeramicCache filter by addr , deleted_at = empty , where stamp []

#     ceramic_cache = CeramicCache.objects.filter(
#         address=address, deleted_at__isnull=True, expiration_date__gt=current_date
#     )
#     # passports = Passport.objects.filter(address=address)

#     # stamps = Stamp.objects.filter(
#     #     passport__in=passports, credential__expirationDate__lt=current_date
#     # )

#     for cc in ceramic_cache:
#         notification_id = dag_cbor.encode(
#             {"stamp_id": stamp.id, "stamp_hash": stamp.hash, "address": address}
#         )
#         notification_exists = Notification.objects.filter(
#             notification_id=notification_id
#         ).exists()

#         if not notification_exists:
#             Notification.objects.create(
#                 notification_id=notification_id,
#                 type="expiry",
#                 is_active=True,
#                 title=f"{stamp.id} Stamp Expired",  # TODO:@Larisa , what the title should look like ?
#                 # TODO: @Larisa how to get stamp name
#                 content=f"Your {stamp.id} stamp has expired. Please reverify to keep your Passport up to date.",
#             )


# def generate_on_chain_passport_expired_notifications(address, passport_data):
#     # TODO: make sure to receive from UI both chain_id and chain_name
#     pass
