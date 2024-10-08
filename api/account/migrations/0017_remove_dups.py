# Generated by Django 4.2.6 on 2024-01-29 23:59

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0016_accountapikey_create_scorers_and_more"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                """delete from account_community as older where exists
                (select 1 from account_community as newer where newer.account_id = older.account_id
                and newer.name = older.name and newer.deleted_at is null and older.deleted_at is null
                and newer.created_at > older.created_at);"""
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
