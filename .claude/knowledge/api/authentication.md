# API Authentication

## API Key Authentication Mechanism

API keys use djangorestframework-api-key (v2) with AbstractAPIKey model.

### Key Storage Structure:
- **Prefix**: First 8 chars for lookup
- **Hashed key**: For security
- **Permissions**: 
  - submit_passports
  - read_scores
  - create_scorers
  - historical_endpoint
- **Rate limits**: Separate for standard, analysis, and embed endpoints
- **Analytics tracking**: Via AccountAPIKeyAnalytics table

### Authentication Flow:
1. Check X-API-Key header first, then Authorization header
2. Look up by prefix, verify against hashed_key
3. Attach to request.api_key for usage tracking
4. Special handling for DEMO_API_KEY_ALIASES

### Database Tables:
- **account_accountapikey**: API key storage with permissions
- **account_accountapikeyanalytics**: Usage tracking with paths, payloads, responses

See `api/registry/api/utils.py` and `api/account/models.py`