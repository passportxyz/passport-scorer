# TypeScript Compilation Check for Pulumi

Before pushing Pulumi infrastructure changes, always verify TypeScript compiles locally to avoid CI failures.

## Quick Check

```bash
cd infra/aws
npx tsc --noEmit
```

This will type-check all TypeScript files without generating output.

## Common Issues

1. **Missing properties in function calls** - Check function signatures in `infra/lib/scorer/new_service.ts`
2. **Type mismatches** - Ensure Pulumi Input/Output types are correct
3. **Import errors** - Verify all imports resolve correctly

## Full Build Check

To run the complete Pulumi workflow locally (requires AWS credentials):

```bash
cd infra/aws
pulumi preview --stack passportxyz/passport-scorer/staging
```

## CI Integration

The GitHub Actions workflow runs `pulumi preview` which includes TypeScript compilation.
Catching errors locally saves time in the CI pipeline.
