# WeightConfiguration CSV Optional Field Handling

## [2025-11-24] WeightConfiguration CSV Optional Field

The WeightConfiguration model has an optional csv_source FileField. The admin's save_model() method was causing a ValueError "The 'csv_source' attribute has no file associated with it" when saving without a CSV file.

### Fix Applied

1. **In save_model()**: Check if obj.csv_source exists AND has a 'file' attribute before processing CSV
2. **In clean_csv_source()**: Return early if no csv_source is provided (it's optional)

### Usage Patterns

This allows WeightConfiguration to be created either:
- **With a CSV file**: Auto-populates WeightConfigurationItems from CSV data
- **Without a CSV file**: Use inline forms to manually add WeightConfigurationItems

See: `api/registry/admin.py`
