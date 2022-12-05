from django.contrib import admin
from .models import Account, Community, AccountAPIKey


class AccountAdmin(admin.ModelAdmin):
    list_display = ("id", "address", "user")


class CommunityAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "description", "account")


class AccountAPIKeyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "prefix", "created", "expiry_date", "revoked")


admin.site.register(Account, AccountAdmin)
admin.site.register(Community, CommunityAdmin)
admin.site.register(AccountAPIKey, AccountAPIKeyAdmin)
