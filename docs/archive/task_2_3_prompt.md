# Phase 2 - Task 2.3: Remove Commented-Out Dependencies

## Context
The `requirements.txt` file contains commented-out dependencies (`httpx` and `tenacity`) that create confusion about their intended use. These dependencies are not used anywhere in the codebase and should be removed to maintain a clean dependency list.

## Current Issues
1. **Commented dependencies cause confusion** - Unclear if they're needed, planned, or deprecated
2. **No references in codebase** - Neither `httpx` nor `tenacity` are imported or used
3. **Alternative already in use** - `aiohttp` is used instead of `httpx`
4. **Maintenance burden** - Unclear if versions should be updated or removed

## Current State

### File: `requirements.txt`

**Lines 28-29:**
```python
# httpx==0.25.2
# tenacity==8.2.3
```

### Analysis Results

**httpx:**
- Commented out in requirements.txt
- `aiohttp==3.9.1` is actively used instead
- No imports found in codebase: `grep -r "import httpx" src/` returns nothing
- No imports found in codebase: `grep -r "from httpx" src/` returns nothing

**tenacity:**
- Commented out in requirements.txt
- Could be useful for retry logic in ORAC Core client, but not implemented
- No imports found in codebase: `grep -r "import tenacity" src/` returns nothing
- No imports found in codebase: `grep -r "from tenacity" src/` returns nothing

## Goal
Clean up `requirements.txt` by removing commented dependencies that serve no purpose. If there's intent to use them in the future, document that properly.

## Implementation Options

### Option 1: Remove Completely (Recommended)
Simply delete the commented lines since they're not used and there's no clear future plan for them.

**Pros:**
- Clean requirements.txt
- No confusion about dependencies
- Easy to add back if needed (git history preserves them)

**Cons:**
- None (can always be restored from git history)

### Option 2: Document Future Intent
If there's a specific plan to use these dependencies, add a comment explaining why they're there.

```python
# Future dependencies (not yet implemented):
# httpx==0.25.2  # TODO: Consider replacing aiohttp for better HTTP/2 support
# tenacity==8.2.3  # TODO: Add retry logic to ORAC Core client (see issue #XX)
```

**Pros:**
- Preserves intention for future work
- Documents potential improvements

**Cons:**
- Requires creating GitHub issues for tracking
- Still somewhat confusing

### Option 3: Create Optional Requirements File
Move planned future dependencies to a separate file like `requirements-future.txt` or `requirements-optional.txt`.

**Pros:**
- Keeps main requirements.txt clean
- Documents potential enhancements without confusion

**Cons:**
- Extra file to maintain
- Probably overkill for just 2 dependencies

## Recommended Approach: Option 1 (Remove Completely)

Given that:
1. These dependencies are not used anywhere
2. There's no documented plan or GitHub issue for them
3. Alternatives are already in use (`aiohttp` instead of `httpx`)
4. Git history preserves them if needed later
5. Adding them back is trivial if needed

**The cleanest solution is to simply remove them.**

## Implementation Steps

1. **Verify non-usage** (already done, but double-check):
   ```bash
   grep -r "import httpx" src/
   grep -r "from httpx" src/
   grep -r "import tenacity" src/
   grep -r "from tenacity" src/
   ```

2. **Remove the commented lines** from `requirements.txt:28-29`

3. **Update documentation** if httpx/tenacity were mentioned anywhere:
   ```bash
   grep -r "httpx" docs/
   grep -r "tenacity" docs/
   ```

4. **Test that installation still works**:
   ```bash
   # On Orin after deployment
   docker exec orac-stt python3.10 -m pip check
   ```

5. **Verify application still works** (run deployment tests)

## Verification Checklist

- [ ] Commented lines removed from requirements.txt
- [ ] No references to httpx in code or docs
- [ ] No references to tenacity in code or docs
- [ ] Application builds successfully
- [ ] Application starts successfully
- [ ] Existing functionality works (health check, STT endpoint)
- [ ] No pip installation warnings or errors

## Files to Modify

**Primary:**
- `requirements.txt` - Lines 28-29 (delete both commented lines)

**Check for references (unlikely to find any):**
- Documentation files (search for httpx/tenacity mentions)
- Comments in code (search for TODO/FIXME referencing these libraries)

## Git Commit Message Template

```
chore: remove unused commented dependencies from requirements.txt

- Remove commented httpx==0.25.2 (aiohttp is used instead)
- Remove commented tenacity==8.2.3 (no retry logic implemented)
- Both dependencies have no imports in codebase
- Can be restored from git history if needed

Addresses cleanup.md section 2.3

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Future Considerations

If retry logic is needed in the future for ORAC Core client:
1. Create GitHub issue documenting the need
2. Evaluate alternatives: `tenacity`, `backoff`, or manual implementation
3. Add to requirements.txt when actually implementing the feature
4. Add tests for retry behavior

If HTTP/2 support becomes necessary:
1. Evaluate if `aiohttp` supports it (it might by now)
2. If switching to `httpx`, do it as a focused PR with testing
3. Document the reason for the switch

## Testing Strategy

### Pre-deployment Testing (Local)
```bash
# 1. Verify lines to remove
grep -n "httpx\|tenacity" requirements.txt

# 2. Check for any references in code
grep -r "httpx" src/ tests/
grep -r "tenacity" src/ tests/
```

### Post-deployment Testing (Orin)
```bash
# 1. Check pip dependencies are satisfied
docker exec orac-stt python3.10 -m pip check

# 2. Verify service health
curl http://orin4:7272/health

# 3. Run deployment tests
cd /home/toby/orac-stt && ./scripts/deploy_and_test.sh
```

## Risk Assessment

**Risk Level:** VERY LOW

**Rationale:**
- Removing commented code has zero runtime impact
- Dependencies are not used anywhere
- Changes are easily reversible via git
- No code changes required, only requirements.txt

**Mitigation:**
- Verify no references in codebase before removing
- Test deployment after removal
- Keep git history for easy restoration

## Expected Outcome

**Before:**
```python
# requirements.txt (lines 26-30)
aiohttp==3.9.1

# httpx==0.25.2
# tenacity==8.2.3

# Development
```

**After:**
```python
# requirements.txt (lines 26-28)
aiohttp==3.9.1

# Development
```

**Benefits:**
- ✅ Cleaner requirements.txt
- ✅ No confusion about intended dependencies
- ✅ Easier to maintain
- ✅ Follows Python best practices (no commented code in requirements)

## Related Cleanup Tasks

This task is part of the larger dependency cleanup effort:
- **Task 1.2**: Split requirements.txt into core/dev/optional files (larger effort)
- **Task 2.3**: Remove commented dependencies (this task - quick win)
- **Future**: Add tenacity if/when retry logic is implemented

This task should be completed before Task 1.2 (splitting requirements) to avoid carrying over commented dependencies into the new structure.

## References

- Cleanup analysis: `cleanup.md` Section 2.3
- Requirements file: `requirements.txt` Lines 28-29
- Python packaging best practices: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
