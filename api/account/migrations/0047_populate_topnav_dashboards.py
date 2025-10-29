# Data migration to populate initial TopNav dashboard configurations with SVG logos

from django.db import migrations


def populate_topnav_dashboards(apps, schema_editor):
    """
    Set up initial TopNav configuration for existing partner dashboards.
    Based on the requirements document, we have 6 partner dashboards that
    should appear in TopNav: Lido, Verax, Shape, Octant, Recall, Linea.
    Includes the SVG logos from the TopNav_Backend_Requirements.md document.
    """
    Customization = apps.get_model('account', 'Customization')

    # Define the partner dashboards with their SVG logos from requirements doc
    partner_configs = [
        {
            'path': 'lido_csm',
            'nav_order': 1,
            'nav_logo': '''<svg width="23" height="23" viewBox="0 0 23 23" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g>
    <path fillRule="evenodd" clipRule="evenodd" d="M11.357 1.5L16.0995 8.92489L11.357 11.6894L6.6148 8.92481L11.357 1.5ZM8.0666 8.57371L11.357 3.42179L14.6477 8.57373L11.357 10.492L8.0666 8.57371Z" fill="#3C82ED"/>
    <path d="M11.35 13.3213L5.8487 10.1142L5.6985 10.3494C4.0041 13.0022 4.3825 16.4764 6.6082 18.7023C9.2274 21.3215 13.474 21.3215 16.0932 18.7023C18.319 16.4764 18.6975 13.0022 17.003 10.3494L16.8528 10.1141L11.35 13.3213Z" fill="#3C82ED"/>
  </g>
</svg>'''
        },
        {
            'path': 'verax',
            'nav_order': 2,
            'nav_logo': '''<svg width="23" height="23" viewBox="0 0 23 23" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g>
    <path d="M7.4262 3.5H2.5L7.0613 14.1574L9.5244 8.60852L7.4262 3.5Z" fill="#FF990A"/>
    <path d="M15.9006 3.5H20.6661L14.2238 19.4861H9.2817L15.9006 3.5Z" fill="#FF990A"/>
  </g>
</svg>'''
        },
        {
            'path': 'shape',
            'nav_order': 3,
            'nav_logo': '''<svg width="23" height="23" viewBox="0 0 23 23" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="11.5" cy="11.5" r="10" fill="black"/>
</svg>'''
        },
        {
            'path': 'octant',
            'nav_order': 4,
            'nav_logo': '''<svg width="23" height="23" viewBox="0 0 23 23" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M11.5 1C19.29 1 22 3.76 22 11.5C22 19.21 19.24 22 11.5 22C3.78 22 1 19.17 1 11.5C1 3.8 3.73 1 11.5 1Z" fill="#171717"/>
  <path fillRule="evenodd" clipRule="evenodd" d="M10.76 12.78C10.28 13.93 9.14 14.73 7.82 14.73C6.05 14.73 4.62 13.31 4.62 11.54C4.62 9.78 6.05 8.35 7.82 8.35C9.14 8.35 10.28 9.16 10.76 10.31C11.27 8.41 12.9 6.98 14.9 6.78C15.23 6.74 15.39 6.77 15.39 7.15V10.04C15.39 10.26 15.35 10.37 14.9 10.37C14.23 10.37 13.8 10.96 13.8 11.54C13.8 12.2 14.19 12.74 14.9 12.74C15.39 12.74 15.39 12.47 15.39 12.13V10.74C15.39 10.48 15.48 10.34 15.73 10.34H17.26C17.5 10.34 17.52 10.35 17.66 10.54C17.66 10.54 18.27 11.39 18.37 11.54C18.48 11.69 18.49 11.74 18.37 11.92C18.26 12.1 17.66 12.94 17.66 12.94C17.52 13.13 17.51 13.14 17.26 13.14H16.11C15.52 13.14 15.39 13.55 15.39 13.92V15.83C15.39 16.28 15.31 16.35 14.9 16.31C12.9 16.1 11.27 14.67 10.76 12.78ZM8.88 11.54C8.88 12.13 8.4 12.61 7.82 12.61C7.23 12.61 6.75 12.13 6.75 11.54C6.75 10.95 7.23 10.48 7.82 10.48C8.4 10.48 8.88 10.95 8.88 11.54Z" fill="white"/>
</svg>'''
        },
        {
            'path': 'recall',
            'nav_order': 5,
            'nav_logo': '''<svg width="23" height="23" viewBox="0 0 23 23" fill="none" xmlns="http://www.w3.org/2000/svg">
  <g>
    <path d="M14.56 13.63C14.77 13.84 15.8 14.83 16.85 15.85C17.9 16.86 19.17 18.08 19.68 18.57L20.61 19.47V21.63H15.99L11.96 17.76V13.23H14.16L14.56 13.63Z" fill="black"/>
    <path d="M4.83 13.25L6.97 15.31C8.15 16.44 9.59 17.84 10.19 18.41L11.27 19.45L11.29 19.47L11.27 21.56L11.27 21.61L8.94 21.62C7.85 21.62 7.27 21.62 6.97 21.62C6.82 21.62 6.73 21.61 6.68 21.61C6.63 21.6 6.6 21.59 6.58 21.57C6.55 21.55 5.66 20.69 4.59 19.66L2.62 17.76V17.74L2.61 15.56C2.61 14.96 2.61 14.41 2.61 14.01C2.61 13.8 2.61 13.64 2.61 13.52C2.61 13.46 2.62 13.42 2.62 13.39C2.62 13.37 2.62 13.36 2.62 13.35C2.62 13.34 2.62 13.34 2.62 13.33C2.62 13.33 2.62 13.33 2.62 13.32L2.64 13.23H4.82L4.83 13.25Z" fill="black"/>
    <path d="M16.49 1.52L16.5 1.52L16.5 1.52L16.76 1.59L16.84 1.62C17.62 1.86 18.3 2.27 18.94 2.87C19.89 3.79 20.47 4.89 20.67 6.18C20.69 6.36 20.71 6.69 20.71 7.01C20.71 7.33 20.7 7.65 20.67 7.83C20.5 8.89 20.09 9.81 19.41 10.67C19.32 10.79 19.08 11.03 18.89 11.22C18.26 11.82 17.67 12.18 16.87 12.44L16.55 12.55L16.54 12.55L2.5 12.55L2.5 11.55C2.5 11.04 2.5 10.79 2.51 10.66C2.52 10.64 2.52 10.63 2.52 10.62C2.51 10.61 2.51 10.6 2.51 10.59C2.5 10.59 2.5 10.58 2.5 10.58C2.5 10.57 2.5 10.56 2.5 10.55C2.5 10.53 2.5 10.52 2.51 10.52C2.51 10.51 2.52 10.5 2.52 10.49C2.53 10.48 2.54 10.46 2.56 10.45C2.59 10.41 2.64 10.36 2.71 10.28C2.85 10.14 3.09 9.91 3.45 9.56L3.65 9.37C3.84 9.19 4 9.04 4.12 8.93C4.2 8.86 4.27 8.8 4.31 8.76C4.33 8.74 4.35 8.73 4.36 8.72C4.37 8.72 4.37 8.71 4.37 8.71L4.35 8.64H11.61C13.23 8.64 14.12 8.64 14.64 8.63C14.98 8.63 15.15 8.62 15.25 8.6C15.35 8.59 15.38 8.57 15.45 8.55C15.59 8.49 15.76 8.38 15.92 8.23C16.08 8.08 16.22 7.9 16.3 7.74C16.43 7.5 16.48 7.27 16.47 6.96C16.47 6.7 16.43 6.52 16.33 6.31L16.31 6.28C16.12 5.9 15.8 5.62 15.41 5.49L15.26 5.43L4.45 5.42H4.43L2.52 3.6V1.5L16.49 1.52Z" fill="black"/>
  </g>
</svg>'''
        },
    ]

    # Update existing customizations if they exist
    for config in partner_configs:
        try:
            customization = Customization.objects.get(path=config['path'])
            customization.show_in_top_nav = True
            customization.nav_order = config['nav_order']
            customization.nav_logo = config['nav_logo']
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
        nav_order=0,
        nav_logo=None
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
