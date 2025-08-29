# Topic Integration TODO

## ORAC Core URL Configuration Feature

### Overview
Add a configuration option in the ORAC STT admin GUI to set the ORAC Core URL, making the system more flexible for different network setups.

### Implementation Plan

#### 1. Backend Changes
- [ ] Add `orac_core_url` to the Settings configuration class with default `http://192.168.8.191:8000`
- [ ] Create API endpoints to get/set the ORAC Core URL configuration
- [ ] Update `heartbeat_manager.py` to properly use the configured URL
- [ ] Store the configuration persistently (in a JSON file or similar)

#### 2. Frontend UI Changes
- [ ] Add a settings/config cog icon next to the existing info (i) icon in the header
- [ ] Create a modal popup for "ORAC Core Configuration" that includes:
  - [ ] Input field for ORAC Core URL (pre-filled with current value)
  - [ ] Test connection button to verify the URL works
  - [ ] Save button to persist the changes
  - [ ] Visual feedback for success/failure

#### 3. Configuration Flow
- When user clicks the config cog → opens modal
- User can edit the ORAC Core URL
- Test button sends a test request to verify connectivity
- Save button updates the backend configuration
- Configuration persists across container restarts

#### 4. Visual Design
- Keep consistent with existing cyberpunk green theme
- Cog icon similar size/style to the info icon
- Modal popup matches existing modal styles
- Success messages in green, errors in red
- Loading states during test/save operations

#### 5. Files to Modify
- `src/orac_stt/config/settings.py` - Add orac_core_url setting
- `src/orac_stt/api/admin.py` - Add config get/set endpoints
- `src/orac_stt/web/static/js/admin.js` - Add config modal logic
- `src/orac_stt/web/static/css/admin.css` - Style the new elements
- `src/orac_stt/web/templates/admin.html` - Add config modal HTML
- `src/orac_stt/integrations/orac_core_client.py` - Use configured URL instead of hardcoded

### Benefits
- Users can easily configure where ORAC STT forwards transcriptions and heartbeats
- Makes the system more flexible for different network setups
- Provides visual feedback for connectivity testing
- Configuration persists across container restarts