# Event Data Structure Gotchas

## [2025-09-09] Score Update Event Data Structure

The SCORE_UPDATE event in Django is created via a pre_save signal on the Score model when status="DONE". The event data contains the serialized Score model using Django's `serializers.serialize("json", [score])`.

Django's serialize function outputs a structure like:
```json
[{
  "model": "registry.score",
  "pk": <primary_key>,
  "fields": {
    "passport": <passport_id>,
    "score": "decimal_value",
    "last_score_timestamp": "ISO timestamp",
    "status": "DONE",
    "error": null,
    "evidence": {...},
    "stamp_scores": {...},
    "stamps": {...},
    "expiration_date": "ISO timestamp"
  }
}]
```

See `api/registry/models.py`