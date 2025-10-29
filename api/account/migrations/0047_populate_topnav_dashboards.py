# Data migration to populate initial TopNav dashboard configurations

from django.db import migrations


def populate_topnav_dashboards(apps, schema_editor):
    """
    Set up initial TopNav configuration for existing partner dashboards.
    Based on the requirements document, we have 6 partner dashboards that
    should appear in TopNav: Lido, Verax, Shape, Octant, Recall, Linea.
    """
    Customization = apps.get_model('account', 'Customization')

    # Define the partner dashboards that should show in TopNav with their order
    partner_configs = [
        {'path': 'lido', 'nav_order': 1},
        {'path': 'verax', 'nav_order': 2},
        {'path': 'shape', 'nav_order': 3},
        {'path': 'octant', 'nav_order': 4},
        {'path': 'recall', 'nav_order': 5},
        {'path': 'linea', 'nav_order': 6},
    ]

    # Update existing customizations if they exist
    for config in partner_configs:
        try:
            customization = Customization.objects.get(path=config['path'])
            customization.show_in_top_nav = True
            customization.nav_order = config['nav_order']
            customization.save()
            print(f"Updated {config['path']} dashboard for TopNav")
        except Customization.DoesNotExist:
            print(f"Dashboard {config['path']} not found, skipping...")


def reverse_topnav_dashboards(apps, schema_editor):
    """
    Reverse the TopNav configuration - hide all dashboards from TopNav.
    """
    Customization = apps.get_model('account', 'Customization')

    # Reset all customizations to not show in TopNav
    Customization.objects.filter(show_in_top_nav=True).update(
        show_in_top_nav=False,
        nav_order=0
    )


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0046_add_topnav_dashboard_fields'),
    ]

    operations = [
        migrations.RunPython(
            populate_topnav_dashboards,
            reverse_topnav_dashboards
        ),
    ]