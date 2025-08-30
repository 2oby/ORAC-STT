# Topic Integration TODO

## ORAC Core URL Configuration Feature

### Overview
Add a configuration option in the ORAC STT admin GUI to set the ORAC Core URL, making the system more flexible for different network setups.

### Implementation Status ✅ COMPLETED

#### 1. Backend Changes ✅
- [x] Add `orac_core_url` to the Settings configuration class with default `http://192.168.8.191:8000` (settings.py:75)
- [x] Create API endpoints to get/set the ORAC Core URL configuration (admin.py:171-271, 397-462)
- [x] Update `heartbeat_manager.py` to properly use the configured URL (heartbeat_manager.py:46-58)
- [x] Store the configuration persistently using settings manager (core/settings_manager.py)

#### 2. Frontend UI Changes ✅
- [x] Add a settings/config cog icon next to the existing info (i) icon in the header (admin.html:32)
- [x] Create a modal popup for "ORAC Core Configuration" that includes: (admin.html:132-158)
  - [x] Input field for ORAC Core URL (pre-filled with current value)
  - [x] Test connection button to verify the URL works
  - [x] Save button to persist the changes
  - [x] Visual feedback for success/failure

#### 3. Configuration Flow ✅
- When user clicks the config cog → opens modal
- User can edit the ORAC Core URL
- Test button sends a test request to verify connectivity
- Save button updates the backend configuration
- Configuration persists across container restarts

#### 4. Visual Design ✅
- Keep consistent with existing cyberpunk green theme
- Cog icon similar size/style to the info icon
- Modal popup matches existing modal styles
- Success messages in green, errors in red
- Loading states during test/save operations

#### 5. Files Modified ✅
- `src/orac_stt/config/settings.py` - Added orac_core_url setting
- `src/orac_stt/api/admin.py` - Added config get/set endpoints
- `src/orac_stt/web/static/js/admin.js` - Added config modal logic
- `src/orac_stt/web/static/css/admin.css` - Styled the new elements
- `src/orac_stt/web/templates/admin.html` - Added config modal HTML
- `src/orac_stt/integrations/orac_core_client.py` - Uses configured URL with settings manager integration

### Benefits
- Users can easily configure where ORAC STT forwards transcriptions and heartbeats
- Makes the system more flexible for different network setups
- Provides visual feedback for connectivity testing
- Configuration persists across container restarts