# Partner Dashboards Architecture

## Dashboard Discovery System

Partner dashboards are implemented through the existing Customization model rather than a separate PartnerDashboard model. This design makes each Customization effectively a dashboard configuration.

### Core Architecture

1. **Single Model Approach**: Each Customization IS a dashboard
   - Path field serves as the dashboard ID for routing
   - No separate PartnerDashboard model needed
   - Discovery layer allows frontend to see available dashboards

2. **TopNav Integration Fields**:
   - `show_in_top_nav`: BooleanField to control TopNav visibility
   - `nav_order`: IntegerField for display ordering (lower = first)
   - Uses `partner_name` field directly (no separate nav_display_name field)

3. **API Response Structure**:
   - Added partnerDashboards as top-level field in customization API response
   - Array order IS the display order (nav_order field not exposed)
   - Returns id (path), name, logo, showInTopNav fields

### Initial Partner Dashboards

5 partner dashboards configured:
- Lido
- Verax
- Shape
- Octant
- Recall

**Note**: Linea was mentioned in migration comment but not actually implemented in the data population.

### Per-Customization Approach

Each customization can have different dashboards displayed, allowing flexible configuration per partner.

### SVG Logo Storage

SVG logos are stored as text in the database with sanitization handled by the frontend.

See: `api/account/models.py`, `api/account/api.py`, `api/account/admin.py`, `app/components/TopNav/components/TopNav.tsx`, `api/account/migrations/0046_add_topnav_dashboard_fields.py`, `api/account/migrations/0047_populate_topnav_dashboards.py`