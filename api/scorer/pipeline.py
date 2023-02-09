from django.contrib.auth.models import Group


def add_social_auth_user_to_group(**kwargs):
    user = kwargs["user"]

    # The @gitcoin.co email requirement is also enforced at the google Oauth layer
    if user.email.endswith("@gitcoin.co"):
        admin_read_only_group = Group.objects.get(name="admin_read_only")
        user.groups.add(admin_read_only_group)
        user.is_staff = True
        user.save()
        return
