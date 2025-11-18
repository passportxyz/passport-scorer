# SQLX Metadata Generation Instructions

## Current State
The SQLX query macros have been stubbed out to allow compilation without DATABASE_URL. This allows the code to compile but database operations won't work until proper SQLX metadata is generated.

## Steps to Generate SQLX Metadata

### 1. Restore Original Query Files
First, restore the original query files that contain the actual SQLX macros:

```bash
# Restore backed up query files
cd rust-scorer
for file in src/db/queries/*.rs.backup; do
    if [ -f "$file" ]; then
        mv "$file" "${file%.backup}"
    fi
done

# Also restore the original weights.rs and scoring.rs from git
git checkout src/db/queries/weights.rs src/db/queries/scoring.rs
```

### 2. Set DATABASE_URL
On a machine with access to the PostgreSQL database containing all the Django tables:

```bash
export DATABASE_URL="postgresql://username:password@host:port/database_name"

# Example for local development:
# export DATABASE_URL="postgresql://postgres:password@localhost:5432/passport_scorer"
```

### 3. Run SQLX Prepare
Generate the offline compilation metadata:

```bash
cd rust-scorer
cargo sqlx prepare
```

This will create a `.sqlx/` directory with JSON files containing query metadata.

### 4. Verify Generated Files
Check that the `.sqlx/` directory was created:

```bash
ls -la .sqlx/
# Should see files like:
# query-*.json files for each query
```

### 5. Commit SQLX Metadata
Add and commit the generated metadata:

```bash
git add .sqlx/
git commit -m "feat: add SQLX offline compilation metadata"
```

## Alternative: Using Docker
If you prefer not to expose database credentials:

```bash
# Run in a Docker container with database access
docker run --rm -it \
    -v $(pwd):/workspace \
    -e DATABASE_URL="postgresql://..." \
    rust:latest \
    bash -c "cd /workspace && cargo sqlx prepare"
```

## Files That Need SQLX Metadata

The following files contain SQLX query macros that need metadata:

### Query Modules (src/db/queries/)
- `weights.rs` - Scorer configuration queries
- `scoring.rs` - Passport and score CRUD operations
- `stamps.rs` - Ceramic cache queries
- `utils.rs` - Allow list and customization queries
- `bans.rs` - Ban checking queries
- `stakes.rs` - GTC staking queries
- `cgrants.rs` - Grants contribution statistics

### Other Modules
- `src/domain/human_points.rs` - Human points recording
- `src/db/ceramic_cache.rs` - Ceramic cache operations
- `src/db/read_ops.rs` - Read operations
- `src/db/write_ops.rs` - Write operations
- `src/auth/api_key.rs` - API key validation

## Troubleshooting

### If SQLX prepare fails:
1. Ensure all tables exist in the database
2. Run Django migrations first:
   ```bash
   cd ../api
   poetry run python manage.py migrate
   ```

### If compilation fails after restoring:
1. Check that DATABASE_URL is set correctly
2. Ensure you're using the same SQLx version
3. Try clearing the cache:
   ```bash
   cargo clean
   rm -rf .sqlx/
   ```

## After SQLX Metadata is Generated

Once the `.sqlx/` directory is committed, the code will compile without DATABASE_URL and can be deployed to any environment. The SQLX offline mode uses the cached metadata for type checking at compile time.

## Current Stub Return Values

The stubbed functions currently return:
- Empty vectors for list queries
- `None` for optional queries
- Default values for required returns
- `Ok(1)` for ID returns

These will be replaced with actual database queries once SQLX metadata is available.