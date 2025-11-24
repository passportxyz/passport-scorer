### [15:40] [gotchas] ALB Listener Rule Priority Conflicts - Third Shift
**Details**: When refactoring infrastructure to use routing-rules.ts, old listener rules persist in AWS even after code is removed. This causes "PriorityInUse" errors when trying to create new rules with the same priorities.

**Solution History**:
1. First shift: V2 API (2021→2110, 2023→2112), Ceramic Cache (1000-1010 → 1011-1020), Embed (2100-2103 → 2104-2106)
2. But old rules still existed at: 1001, 1002, 1003, 1004, 1006, 1007, 1010, 1012, 1015, 2021, 2023, 2100, 2101, 2103
3. Second shift (2025-11-24): Ceramic Cache range shifted again (1011-1020 → 1030-1039) to skip ALL old rules

**Current Priority Assignments**:
- V2 API: 2110 (models-score), 2112 (stamps-score)
- Ceramic Cache: 1030-1039 (submit, score, stamps bulk, weights, etc.)
- Embed (internal ALB): 2104-2106
- App API: 3000-3001

**Old priorities to avoid**: 1001-1020, 2021, 2023, 2100-2103

**Long-term fix**: Delete old AWS listener rules manually or via AWS CLI when safe to do so.
**Files**: infra/lib/scorer/routing-rules.ts
---

