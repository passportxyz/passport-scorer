# TopNav Dashboard Discovery API

## Implementation Details

### Database Schema

Added 3 fields to Customization model:
- **show_in_top_nav**: BooleanField to control TopNav visibility
- **nav_order**: IntegerField for display ordering (lower values appear first)
- **nav_display_name**: CharField for custom display name (optional, falls back to partner_name)

### API Endpoint Modification

The `/account/customization/{dashboard_path}/` endpoint now returns:

1. **Current dashboard's customization data**: All existing fields
2. **partnerDashboards array**: List of all TopNav-visible dashboards

#### Partner Dashboards Array Structure
```json
{
  "partnerDashboards": [
    {
      "id": "path_field_value",  // Used for routing
      "name": "display_name",     // nav_display_name or partner_name
      "logo": "svg_string",
      "showInTopNav": true
    }
  ]
}
```

### Query Implementation

- Queries all customizations with `show_in_top_nav=True`
- Orders by `nav_order`, then `partner_name`
- Array order in response IS the display order (nav_order field not exposed to frontend)

### Django Admin Configuration

Added TopNav Configuration section:
- Collapsible fieldset containing the 3 new fields
- Added `show_in_top_nav` and `nav_order` to list_display
- Allows easy management of which dashboards appear in TopNav

### Frontend Integration Pattern

1. Call `/account/customization/{dashboard_path}/` to get both:
   - Current dashboard's customization data
   - partnerDashboards array with all TopNav-visible dashboards
2. Filter dashboards where `showInTopNav=true` for display
3. Use the array order as-is for display order

### Migration Files

- `0046_add_topnav_dashboard_fields.py`: Schema changes
- `0047_populate_topnav_dashboards.py`: Initial data population

See: `api/account/api.py`, `api/account/models.py`, `api/account/admin.py`