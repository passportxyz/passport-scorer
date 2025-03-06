"""
This module contains functions for managing user groups and permissions in the context of social authentication.
It specifically handles group assignments for users with "@passport.xyz" email addresses.
"""

from django.contrib.auth.models import Group


def add_social_auth_user_to_group(**kwargs):
    user = kwargs["user"]

    # The @passport.xyz email requirement is also enforced at the google Oauth layer
    if user.email.endswith("@passport.xyz") or user.email.endswith("@holonym.id"):
        admin_read_only_group = Group.objects.get(name="admin_read_only")
        user.groups.add(admin_read_only_group)
        user.is_staff = True
        user.save()
        return
