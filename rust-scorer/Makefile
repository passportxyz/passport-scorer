.PHONY: build-lambda
build-lambda:
	@echo "Building Lambda function..."
	@./scripts/build-lambda-zip.sh

.PHONY: verify-lambda
verify-lambda:
	@echo "Verifying Lambda package..."
	@./scripts/verify-lambda-package.sh

.PHONY: help
help:
	@echo "Available targets:"
	@echo "  build-lambda      - Build Lambda function as zip artifact for ARM64"
	@echo "  verify-lambda     - Verify Lambda package contents"
