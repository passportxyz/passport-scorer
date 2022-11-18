from django.contrib import admin

from registry.models import Passport, Stamp


class PassportAdmin(admin.ModelAdmin):
    list_display = ["did", "version"]
    search_fields = ["did"]


class StampAdmin(admin.ModelAdmin):
    list_display = ["passport", "provider", "hash"]
    search_fields = ["passport__did", "provider", "hash"]


admin.site.register(Passport, PassportAdmin)
admin.site.register(Stamp, StampAdmin)
