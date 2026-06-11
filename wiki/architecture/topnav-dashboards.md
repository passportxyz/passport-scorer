# TopNav Dashboard Discovery

Customization model fields and API response for dashboard navigation in partner interfaces.

## Schema Fields

Added to Customization model:

- **show_in_top_nav**: BooleanField, controls TopNav visibility
- **nav_order**: IntegerField, display ordering (lower = first)
- **nav_display_name**: CharField, custom display name (optional, falls back to partner_name)

## API Response

GET /account/customization/{dashboard_path}/ returns:

```json
{
  "partnerDashboards": [
    {
      "id": "path_field_value",
      "name": "display_name",
      "logo": "svg_string",
      "showInTopNav": true
    }
  ]
}
```

Plus all existing customization data.

## Query Implementation

- Queries all customizations with show_in_top_nav=True
- Orders by nav_order, then partner_name
- Array order in response IS the display order
- nav_order field not exposed to frontend

## Admin Configuration

Added TopNav Configuration fieldset:
- Collapsible section with the 3 fields
- show_in_top_nav and nav_order in list_display
- Enables easy dashboard management

## Frontend Integration

1. Call /account/customization/{dashboard_path}/
2. Filter where showInTopNav=true
3. Use array order as-is for display

## Migrations

- 0046_add_topnav_dashboard_fields.py: Schema changes
- 0047_populate_topnav_dashboards.py: Initial data population
