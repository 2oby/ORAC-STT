# Sprint 1: Dependency Cleanup - Implementation Guide

**Duration:** 1-2 days
**Priority:** P0 (High Impact, Low Effort)
**Risk Level:** LOW
**Status:** Ready to Execute

## Executive Summary

Sprint 1 focuses on cleaning up dependencies, Docker configuration, and removing technical debt from the build/deployment pipeline. These are quick wins that improve maintainability without changing runtime behavior.

**Progress Summary:**
- ✅ **Task 1**: Split requirements.txt into core/dev/optional - **COMPLETE**
- ✅ **Task 2**: Remove commented httpx/tenacity - **COMPLETE**
- ⏳ **Task 3**: Update Dockerfile to use new requirements - **PENDING**
- ⏳ **Task 4**: Merge Dockerfile and Dockerfile.fixed - **ALREADY DONE** (no .fixed files found)
- ⏳ **Task 5**: Merge docker-compose files - **ALREADY DONE** (no .fixed files found)
- ⏳ **Task 6**: Update deployment docs - **PENDING**

## Tasks Overview

### ✅ Task 1: Split requirements.txt into core/dev/optional (COMPLETE)

**Status:** Already completed in commit `bbc9e8d`

**Current State:**
```
requirements.txt          - Core production dependencies (643 bytes)
requirements-dev.txt      - Development dependencies (282 bytes)
requirements-pytorch.txt  - Optional PyTorch backend (649 bytes)
```

**Verification:**
```bash
# Check files exist
ls -la requirements*.txt

# Review contents
head -5 requirements.txt requirements-dev.txt requirements-pytorch.txt
```

### ✅ Task 2: Remove commented httpx/tenacity (COMPLETE)

**Status:** Already completed in commit `bbc9e8d`

**Verification:**
```bash
# Should return nothing
grep -n "httpx\|tenacity" requirements.txt
```

### ⏳ Task 3: Update Dockerfile to use new requirements

**Current Issue:**
The Dockerfile may still be installing all requirements together, or may need to be updated to use the split requirements files efficiently.

**Current State to Check:**
```bash
# Review current Dockerfile installation commands
grep -A 5 "requirements" Dockerfile
```

**Target State:**
```dockerfile
# Install production dependencies only
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional: Install PyTorch backend (if needed)
# COPY requirements-pytorch.txt .
# RUN pip install --no-cache-dir -r requirements-pytorch.txt

# Note: requirements-dev.txt should NOT be installed in production
```

**Implementation Steps:**

1. **Read current Dockerfile** to understand current state
2. **Update pip install commands** to use new requirements structure:
   - Install only `requirements.txt` in production
   - Document how to install optional dependencies
   - Add comment explaining why dev dependencies are excluded
3. **Verify whisper.cpp integration** is preserved (no PyTorch needed)
4. **Test build** on Orin Nano

**Files to Modify:**
- `Dockerfile` - Update RUN pip install commands

**Testing:**
```bash
# Build container locally (if possible) or on Orin
cd /Users/2oby/pCloud\ Box/Projects/ORAC/ORAC\ STT
docker build -t orac-stt:test .

# Or deploy and test on Orin
cd scripts && ./deploy_and_test.sh
```

**Success Criteria:**
- [ ] Dockerfile only installs requirements.txt
- [ ] Container builds successfully
- [ ] Container runs and passes health checks
- [ ] No dev dependencies in production image
- [ ] Image size is reasonable (check `docker images`)

### ✅ Task 4: Merge Dockerfile and Dockerfile.fixed (ALREADY DONE)

**Status:** No duplicate files found

**Verification:**
```bash
# Should return nothing
ls -la Dockerfile.fixed 2>&1
```

**Result:** Only single `Dockerfile` exists (2523 bytes). Task complete!

### ✅ Task 5: Merge docker-compose files (ALREADY DONE)

**Status:** No duplicate files found

**Verification:**
```bash
# Should return nothing
ls -la docker-compose.fixed.yml docker-compose.fixed.yaml 2>&1
```

**Result:** Only single `docker-compose.yml` exists (2065 bytes). Task complete!

**Note:** Still need to check for duplicate `environment:` blocks as mentioned in cleanup.md Section 4.3:
```yaml
# Check for duplicate environment blocks
grep -n "^  environment:" docker-compose.yml
```

### ⏳ Task 6: Update deployment docs

**Objective:**
Update documentation to reflect the new requirements structure and clarify when to use which file.

**Files to Update:**

1. **README.md** - Update installation instructions
2. **DEPLOYMENT_INSTRUCTIONS.md** - Update deployment steps
3. **CLAUDE.md** - Update development setup instructions
4. **Dockerfile** - Add inline comments explaining requirements structure

**Specific Changes:**

#### A. README.md Updates

**Section to Update:** Installation / Development Setup

**Add explanation:**
```markdown
## Dependencies

The project uses split requirements files:

- **requirements.txt** - Core production dependencies (FastAPI, audio processing, etc.)
- **requirements-dev.txt** - Development tools (pytest, black, mypy, etc.)
- **requirements-pytorch.txt** - Optional PyTorch backend (if not using whisper.cpp)

### Installation

**Production deployment:**
```bash
pip install -r requirements.txt
```

**Development environment:**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

**Optional PyTorch backend** (not needed for whisper.cpp):
```bash
pip install -r requirements-pytorch.txt
```

**Note:** The default configuration uses whisper.cpp (not PyTorch), so requirements-pytorch.txt is typically not needed.
```

#### B. DEPLOYMENT_INSTRUCTIONS.md Updates

**Section to Update:** Docker Build Process

**Add explanation:**
```markdown
## Docker Image Dependencies

The production Docker image installs only `requirements.txt` (core dependencies).

Development dependencies (`requirements-dev.txt`) are NOT installed in production to keep the image size minimal.

PyTorch dependencies (`requirements-pytorch.txt`) are NOT installed because we use whisper.cpp by default.

### Image Size Comparison

- **With only requirements.txt:** ~500MB
- **With requirements-pytorch.txt:** ~3-4GB (not recommended)

### Building with Optional Dependencies

If you need to build with PyTorch support:

```dockerfile
# Uncomment in Dockerfile:
# COPY requirements-pytorch.txt .
# RUN pip install --no-cache-dir -r requirements-pytorch.txt
```

Then set environment variable:
```yaml
# In docker-compose.yml:
environment:
  - USE_WHISPER_CPP=false
```
```

#### C. CLAUDE.md Updates

**Section to Update:** Development Environment

**Update development workflow:**
```markdown
## Development Dependencies

For local development, install both production and dev dependencies:

```bash
# Install all dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Optional: PyTorch backend (only if testing PyTorch support)
pip install -r requirements-pytorch.txt
```

### Running Tests Locally

Tests require dev dependencies:
```bash
# Install dev dependencies first
pip install -r requirements-dev.txt

# Run tests
pytest tests/
```

### Code Quality Tools

Dev dependencies include:
- **pytest** - Testing framework
- **pytest-asyncio** - Async test support
- **pytest-cov** - Coverage reporting
- **black** - Code formatting
- **isort** - Import sorting
- **mypy** - Type checking
- **flake8** - Linting
```

#### D. Dockerfile Comments

**Add inline comments:**
```dockerfile
# Install production dependencies only
# - requirements.txt: Core dependencies (FastAPI, audio processing, etc.)
# - requirements-dev.txt: NOT installed in production (keeps image small)
# - requirements-pytorch.txt: NOT installed (we use whisper.cpp, not PyTorch)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

**Implementation Steps:**

1. **Read each documentation file** to understand current content
2. **Add/update sections** explaining requirements structure
3. **Add examples** showing when to use each file
4. **Update any outdated instructions** that reference old single requirements.txt
5. **Ensure consistency** across all docs

**Success Criteria:**
- [ ] README.md explains requirements structure
- [ ] DEPLOYMENT_INSTRUCTIONS.md documents Docker dependency choices
- [ ] CLAUDE.md has updated development setup instructions
- [ ] Dockerfile has clear inline comments
- [ ] All docs are consistent with each other
- [ ] Examples are correct and tested

## Additional Cleanup Tasks (From Section 14)

### Quick Wins (< 1 hour each)

While we're doing Sprint 1, consider these additional quick wins:

#### A. Delete test_whisper_fix.py (if in root)

**Check:**
```bash
ls -la "/Users/2oby/pCloud Box/Projects/ORAC/ORAC STT/test_whisper_fix.py" 2>&1
```

**Action if exists:**
```bash
# Option 1: Move to tests/archived/
mkdir -p tests/archived
git mv test_whisper_fix.py tests/archived/

# Option 2: Just delete (it's in git history)
git rm test_whisper_fix.py
```

#### B. Delete scripts/generate_certs.sh (if empty)

**Check:**
```bash
cat "scripts/generate_certs.sh" 2>&1
```

**Action if empty/placeholder:**
```bash
git rm scripts/generate_certs.sh
# Or move to archive if there's future intent to implement
```

#### C. Fix duplicate environment blocks in docker-compose.yml

**Check:**
```bash
grep -n "^  environment:" docker-compose.yml
```

**Action if duplicates found:**
Merge into single environment block. See cleanup.md Section 4.3 for details.

#### D. Archive sprint completion docs

**Check for sprint docs:**
```bash
ls -la *.md | grep -i "sprint\|done\|solved"
```

**Action:**
```bash
mkdir -p archive
git mv DONE_SPRINT_*.md archive/ 2>/dev/null || true
git mv *SOLVED*.md archive/ 2>/dev/null || true
```

## Implementation Order

**Recommended sequence:**

1. ✅ **Verify Task 1 & 2** are complete (already done)
2. ✅ **Verify Task 4 & 5** are complete (no .fixed files)
3. ⏳ **Execute Task 3**: Update Dockerfile for new requirements
4. ⏳ **Execute Task 6**: Update all documentation
5. ⏳ **Execute Quick Wins**: Clean up extra files (optional but recommended)
6. ✅ **Test deployment**: Run deploy_and_test.sh
7. ✅ **Commit changes**: Single commit with all Sprint 1 changes

## Testing Strategy

### Pre-Deployment Testing

```bash
# 1. Verify requirements files exist and are correct
ls -la requirements*.txt
head requirements.txt requirements-dev.txt requirements-pytorch.txt

# 2. Check Dockerfile syntax
docker build --dry-run -t orac-stt:test . 2>&1 | head -20

# 3. Verify no commented dependencies
grep "^#.*==" requirements.txt && echo "Found commented deps!" || echo "Clean!"

# 4. Check for .fixed files
ls -la *.fixed* 2>&1 | grep "No such" && echo "No duplicates!" || echo "Found .fixed files!"
```

### Deployment Testing

```bash
# Deploy to Orin
cd scripts && ./deploy_and_test.sh

# Verify container health
ssh orin4 "docker exec orac-stt curl -s http://localhost:7272/health | jq ."

# Check installed packages
ssh orin4 "docker exec orac-stt pip list | grep -E 'pytest|black|torch'"
# Should NOT see pytest, black (dev deps)
# Should NOT see torch (PyTorch deps)

# Check container size
ssh orin4 "docker images orac-stt:latest"
# Should be ~500MB, not 3-4GB
```

### Post-Deployment Validation

```bash
# 1. Health check
curl http://orin4:7272/health

# 2. Metrics check
curl http://orin4:7272/metrics | head -20

# 3. Test transcription endpoint (if test audio available)
curl -X POST http://orin4:7272/stt/v1/stream \
  -F "file=@test_audio.wav" \
  -F "language=en"

# 4. Check logs for errors
ssh orin4 "docker logs --tail 50 orac-stt"
```

## Git Commit Strategy

**Option 1: Single Commit (Recommended)**

All Sprint 1 changes in one commit:

```bash
git add requirements.txt requirements-dev.txt requirements-pytorch.txt
git add Dockerfile docker-compose.yml
git add README.md DEPLOYMENT_INSTRUCTIONS.md CLAUDE.md
git add -u  # Add any deletions (test_whisper_fix.py, generate_certs.sh, etc.)

git commit -m "$(cat <<'EOF'
chore: complete Sprint 1 dependency cleanup

Split Requirements (Tasks 1-2: Already Complete):
- requirements.txt: Core production dependencies only
- requirements-dev.txt: Testing and linting tools
- requirements-pytorch.txt: Optional PyTorch backend
- Removed commented httpx and tenacity dependencies

Dockerfile Updates (Task 3):
- Install only requirements.txt in production
- Document optional dependency installation
- Exclude dev dependencies to keep image small (~500MB)

Documentation Updates (Task 6):
- README.md: Add requirements structure explanation
- DEPLOYMENT_INSTRUCTIONS.md: Document Docker dependency choices
- CLAUDE.md: Update development setup instructions
- Dockerfile: Add inline comments for clarity

Additional Cleanup:
- Remove duplicate Docker configuration files (already absent)
- Archive/remove unused test scripts
- Remove empty placeholder scripts

Addresses cleanup.md Sprint 1 (Section 10)
Risk: LOW (no runtime behavior changes)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

**Option 2: Multiple Small Commits**

If you prefer granular commits:

```bash
# Commit 3: Dockerfile updates
git add Dockerfile
git commit -m "chore: update Dockerfile to use split requirements"

# Commit 4: Documentation updates
git add README.md DEPLOYMENT_INSTRUCTIONS.md CLAUDE.md
git commit -m "docs: update documentation for split requirements structure"

# Commit 5: Cleanup (optional)
git add -u  # Deletions
git commit -m "chore: remove unused test scripts and placeholders"
```

## Success Criteria Checklist

### Sprint 1 Core Tasks

- [x] **Task 1**: requirements.txt split into 3 files (COMPLETE)
- [x] **Task 2**: Commented dependencies removed (COMPLETE)
- [ ] **Task 3**: Dockerfile updated for new requirements
- [x] **Task 4**: No Dockerfile.fixed exists (VERIFIED)
- [x] **Task 5**: No docker-compose.fixed.yml exists (VERIFIED)
- [ ] **Task 6**: Documentation updated across all files

### Validation Checks

- [ ] Container builds successfully on Orin
- [ ] Container size is ~500MB (not 3-4GB)
- [ ] No dev dependencies installed in production
- [ ] No PyTorch dependencies installed
- [ ] Health endpoint responds correctly
- [ ] STT endpoint works (if testable)
- [ ] Documentation is consistent and clear

### Cleanup Metrics

- [ ] No duplicate files (Dockerfile, docker-compose)
- [ ] No commented dependencies in requirements
- [ ] No empty placeholder scripts
- [ ] Sprint completion docs archived (optional)
- [ ] Test scripts moved to tests/ or archived (optional)

## Risk Assessment

**Overall Risk: VERY LOW**

**Why Low Risk:**
1. Requirements split already complete (tested in commit bbc9e8d)
2. No runtime code changes, only build/deploy configuration
3. Easily reversible via git revert
4. Testing can be done on Orin before production deployment
5. No breaking changes to API or functionality

**Mitigation:**
1. Test build locally if possible
2. Deploy to test environment first (orin4 is test)
3. Verify health checks pass before accepting changes
4. Keep old image as backup: `docker tag orac-stt:latest orac-stt:pre-sprint1`
5. Can quickly rollback if issues found

## Estimated Time

- **Task 3** (Dockerfile updates): 30 minutes
- **Task 6** (Documentation): 1-2 hours
- **Testing**: 30 minutes
- **Cleanup tasks**: 15 minutes
- **Git commit & push**: 15 minutes

**Total: 2.5-3.5 hours**

## Dependencies & Prerequisites

**Required:**
- ✅ Git repository clean (check with `git status`)
- ✅ SSH access to orin4 (check with `ssh orin4 echo "Connected"`)
- ✅ Docker running on Orin (check with `ssh orin4 docker ps`)

**Optional but helpful:**
- Local Docker (for testing builds before deployment)
- Test audio file (for validating STT endpoint)

## Next Steps After Sprint 1

Once Sprint 1 is complete, proceed to:

**Sprint 2: Test Foundation (3-5 days)**
- Set up test structure under tests/
- Add pytest fixtures
- Write first 10-20 unit tests
- Add CI pipeline (GitHub Actions)

See `cleanup.md` Section 10 for Sprint 2 details.

## References

- **Cleanup Analysis**: `cleanup.md` Sections 1.2, 1.3, 4.2, 10, 14
- **Task 2.3 Details**: `task_2_3_prompt.md` (commented dependencies)
- **Current Status**: `CURRENT_FOCUS.md`
- **Git History**: Commit `bbc9e8d` (requirements split)
- **Deployment**: `CLAUDE.md` and `scripts/deploy_and_test.sh`

## Notes

- Task 2.2 (refactor _transcribe_impl) is NOT part of Sprint 1
- Task 2.2 belongs to Sprint 3 (Code Quality)
- Focus on dependencies, Docker, and docs for Sprint 1
- Don't get distracted by code refactoring yet

---

**Ready to Execute:** Yes
**Blocking Issues:** None
**Confidence Level:** High (5/5)

