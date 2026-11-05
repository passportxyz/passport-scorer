# Partner Dashboards

Partner dashboards are Customization model instances with TopNav metadata. Single model approach with discovery via API.

## Architecture

Each `Customization` is a dashboard:
- `path`: Unique dashboard ID for routing
- `partner_name`: Display name in TopNav
- `show_in_top_nav`: BooleanField controlling visibility
- `nav_order`: IntegerField for display ordering (lower = first)

API returns `partnerDashboards` array in customization response with fields: id, name, logo, showInTopNav. Array order is display order.

## Initial Dashboards

5 partner dashboards configured:
- Lido
- Verax
- Shape
- Octant
- Recall

## Per-Customization Configuration

Each customization can display different dashboards, allowing flexible per-partner setup.

## Admin

Added TopNav Configuration fieldset in CustomizationAdmin with show_in_top_nav and nav_order fields.

Migrations: `api/account/migrations/0046_add_topnav_dashboard_fields.py`, `0047_populate_topnav_dashboards.py`

Model: `api/account/models.py`

API response: `api/account/api.py` GET /account/customization/{dashboard_path}/

Frontend: TopNav.tsx reads partnerDashboards array where showInTopNav=true
