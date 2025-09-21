// Backend Management Module for ORAC STT Admin

class BackendManager {
    constructor(admin) {
        this.admin = admin;
        this.backends = new Map();
        this.currentBackendId = null;
        this.currentEntities = new Map();
    }

    // Initialize backend manager
    async init() {
        await this.loadBackends();
        this.setupEventListeners();
    }

    // Setup event listeners
    setupEventListeners() {
        // Search and filter for entities
        const searchInput = document.getElementById('entitySearch');
        const filterSelect = document.getElementById('entityTypeFilter');

        if (searchInput) {
            searchInput.addEventListener('input', () => this.filterEntities());
        }

        if (filterSelect) {
            filterSelect.addEventListener('change', () => this.filterEntities());
        }
    }

    // Load all backends
    async loadBackends() {
        try {
            const response = await fetch('/api/backends');
            if (response.ok) {
                const backends = await response.json();
                this.backends.clear();
                backends.forEach(backend => {
                    this.backends.set(backend.id, backend);
                });
                this.renderBackendsList();
            } else {
                console.error('Failed to load backends');
            }
        } catch (error) {
            console.error('Error loading backends:', error);
        }
    }

    // Render backends list
    renderBackendsList() {
        const backendsList = document.getElementById('backendsList');
        const emptyState = document.getElementById('backendsEmptyState');

        if (!backendsList || !emptyState) return;

        backendsList.innerHTML = '';

        if (this.backends.size === 0) {
            backendsList.style.display = 'none';
            emptyState.style.display = 'block';
        } else {
            backendsList.style.display = 'grid';
            emptyState.style.display = 'none';

            this.backends.forEach(backend => {
                const card = this.createBackendCard(backend);
                backendsList.appendChild(card);
            });
        }
    }

    // Create backend card element
    createBackendCard(backend) {
        const template = document.getElementById('backendCardTemplate');
        const card = template.content.cloneNode(true);

        const cardElement = card.querySelector('.backend-card');
        cardElement.dataset.backendId = backend.id;

        card.querySelector('.backend-name').textContent = backend.name;
        card.querySelector('.backend-url').textContent = `${backend.connection.url}:${backend.connection.port}`;

        const statusIndicator = card.querySelector('.backend-status-indicator');
        if (backend.status.connected) {
            statusIndicator.classList.add('connected');
        }

        // Update statistics
        const stats = backend.statistics || {};
        card.querySelector('.entity-count').textContent = stats.total_entities || 0;
        card.querySelector('.enabled-count').textContent = stats.enabled_entities || 0;

        return cardElement;
    }

    // Show add backend modal
    showAddBackendModal() {
        const modal = document.getElementById('addBackendModal');
        if (modal) {
            modal.style.display = 'block';
            // Reset form
            document.getElementById('backendName').value = '';
            document.getElementById('backendUrl').value = '';
            document.getElementById('backendPort').value = '8123';
            document.getElementById('backendToken').value = '';
            document.getElementById('connectionTestStatus').style.display = 'none';
            document.getElementById('saveBackendBtn').disabled = true;
        }
    }

    // Close add backend modal
    closeAddBackendModal() {
        const modal = document.getElementById('addBackendModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    // Test backend connection
    async testBackendConnection() {
        const name = document.getElementById('backendName').value;
        const url = document.getElementById('backendUrl').value;
        const port = document.getElementById('backendPort').value;
        const token = document.getElementById('backendToken').value;

        if (!name || !url || !port || !token) {
            this.showStatus('connectionTestStatus', 'Please fill in all fields', 'error');
            return;
        }

        this.showStatus('connectionTestStatus', 'Testing connection...', 'loading');

        try {
            // First create the backend
            const createResponse = await fetch('/api/backends', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    url: url,
                    port: parseInt(port),
                    token: token
                })
            });

            if (!createResponse.ok) {
                throw new Error('Failed to create backend');
            }

            const backend = await createResponse.json();

            // Then test the connection
            const testResponse = await fetch(`/api/backends/${backend.id}/test`, {
                method: 'POST'
            });

            if (!testResponse.ok) {
                throw new Error('Connection test failed');
            }

            const status = await testResponse.json();

            if (status.connected) {
                this.showStatus('connectionTestStatus',
                    `✓ Connected successfully! Version: ${status.version}`, 'success');
                document.getElementById('saveBackendBtn').disabled = false;
                // Store the backend ID for saving
                document.getElementById('saveBackendBtn').dataset.backendId = backend.id;
            } else {
                this.showStatus('connectionTestStatus',
                    `✗ Connection failed: ${status.error}`, 'error');
                // Delete the backend if connection failed
                await fetch(`/api/backends/${backend.id}`, { method: 'DELETE' });
            }
        } catch (error) {
            this.showStatus('connectionTestStatus',
                `✗ Error: ${error.message}`, 'error');
        }
    }

    // Test existing backend
    async testBackend(button) {
        const card = button.closest('.backend-card');
        const backendId = card.dataset.backendId;

        button.textContent = 'TESTING...';
        button.disabled = true;

        try {
            const response = await fetch(`/api/backends/${backendId}/test`, {
                method: 'POST'
            });

            const status = await response.json();

            const indicator = card.querySelector('.backend-status-indicator');
            if (status.connected) {
                indicator.classList.add('connected');
                button.textContent = 'CONNECTED';
                setTimeout(() => {
                    button.textContent = 'TEST';
                    button.disabled = false;
                }, 2000);
            } else {
                indicator.classList.remove('connected');
                button.textContent = 'FAILED';
                setTimeout(() => {
                    button.textContent = 'TEST';
                    button.disabled = false;
                }, 2000);
            }
        } catch (error) {
            button.textContent = 'ERROR';
            setTimeout(() => {
                button.textContent = 'TEST';
                button.disabled = false;
            }, 2000);
        }
    }

    // Save backend and proceed to entity configuration
    async saveBackend() {
        const backendId = document.getElementById('saveBackendBtn').dataset.backendId;

        if (!backendId) {
            this.showStatus('connectionTestStatus', 'Please test connection first', 'error');
            return;
        }

        this.closeAddBackendModal();
        await this.loadBackends();

        // Open entity configuration for this backend
        this.configureEntities({ closest: () => ({ dataset: { backendId } }) });
    }

    // Configure entities for a backend
    async configureEntities(button) {
        const card = button.closest ? button.closest('.backend-card') : button.closest();
        const backendId = card.dataset.backendId;

        this.currentBackendId = backendId;
        const backend = this.backends.get(backendId);

        if (!backend) return;

        const modal = document.getElementById('entityConfigModal');
        const backendNameSpan = document.getElementById('entityConfigBackendName');

        if (modal && backendNameSpan) {
            backendNameSpan.textContent = backend.name;
            modal.style.display = 'block';

            // Load existing entities
            await this.loadEntities(backendId);
        }
    }

    // Close entity configuration modal
    closeEntityConfigModal() {
        const modal = document.getElementById('entityConfigModal');
        if (modal) {
            modal.style.display = 'none';
        }
        this.currentBackendId = null;
        this.currentEntities.clear();
    }

    // Fetch entities from Home Assistant
    async fetchEntities() {
        if (!this.currentBackendId) return;

        const entitiesList = document.getElementById('entitiesList');
        if (entitiesList) {
            entitiesList.innerHTML = '<div class="loading-text">Fetching entities from Home Assistant...</div>';
        }

        try {
            const response = await fetch(`/api/backends/${this.currentBackendId}/entities/fetch`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error('Failed to fetch entities');
            }

            const result = await response.json();

            if (result.success) {
                await this.loadEntities(this.currentBackendId);
                this.showNotification('Entities fetched successfully!', 'success');
            } else {
                throw new Error(result.error || 'Unknown error');
            }
        } catch (error) {
            if (entitiesList) {
                entitiesList.innerHTML = `<div class="error-text">Error: ${error.message}</div>`;
            }
            this.showNotification(`Error fetching entities: ${error.message}`, 'error');
        }
    }

    // Load entities for a backend
    async loadEntities(backendId) {
        try {
            const response = await fetch(`/api/backends/${backendId}/entities`);

            if (!response.ok) {
                throw new Error('Failed to load entities');
            }

            const data = await response.json();

            this.currentEntities.clear();
            Object.entries(data.entities || {}).forEach(([id, entity]) => {
                this.currentEntities.set(id, entity);
            });

            this.renderEntities();
            this.updateEntityStats(data.statistics || {});
        } catch (error) {
            console.error('Error loading entities:', error);
        }
    }

    // Render entities list
    renderEntities() {
        const entitiesList = document.getElementById('entitiesList');
        if (!entitiesList) return;

        entitiesList.innerHTML = '';

        if (this.currentEntities.size === 0) {
            entitiesList.innerHTML = '<div class="empty-state">No entities found. Click "FETCH ENTITIES" to import from Home Assistant.</div>';
            return;
        }

        this.currentEntities.forEach((entity, entityId) => {
            const card = this.createEntityCard(entityId, entity);
            entitiesList.appendChild(card);
        });

        this.filterEntities();
    }

    // Create entity card element
    createEntityCard(entityId, entity) {
        const template = document.getElementById('entityCardTemplate');
        const card = template.content.cloneNode(true);

        const cardElement = card.querySelector('.entity-card');
        cardElement.dataset.entityId = entityId;

        if (entity.enabled) {
            cardElement.classList.add('enabled');
        }

        // Set checkbox state
        const checkbox = card.querySelector('.entity-enable-checkbox');
        checkbox.checked = entity.enabled;

        // Set icon based on domain
        const icon = card.querySelector('.entity-icon');
        icon.textContent = this.getEntityIcon(entity.domain);

        // Set entity details
        card.querySelector('.entity-id').textContent = entityId;
        card.querySelector('.entity-type').textContent = `Type: ${entity.domain}`;

        if (entity.area) {
            card.querySelector('.entity-area').textContent = `Area: ${entity.area}`;
        } else {
            card.querySelector('.entity-area').textContent = '';
        }

        card.querySelector('.entity-state').textContent = `Original: ${entity.original_name}`;

        // Set friendly name input
        const nameInput = card.querySelector('.entity-name-input');
        nameInput.value = entity.friendly_name || '';
        nameInput.dataset.entityId = entityId;

        // Add change listener for friendly name
        nameInput.addEventListener('change', (e) => {
            this.updateEntityFriendlyName(entityId, e.target.value);
        });

        return cardElement;
    }

    // Get icon for entity domain
    getEntityIcon(domain) {
        const icons = {
            light: '💡',
            switch: '🔌',
            climate: '🌡️',
            scene: '🎬',
            sensor: '📊',
            binary_sensor: '🔍',
            cover: '🪟',
            fan: '💨',
            lock: '🔒',
            media_player: '🎵',
            automation: '🤖'
        };
        return icons[domain] || '📦';
    }

    // Toggle entity enabled state
    async toggleEntity(checkbox) {
        const card = checkbox.closest('.entity-card');
        const entityId = card.dataset.entityId;
        const enabled = checkbox.checked;

        if (enabled) {
            card.classList.add('enabled');
        } else {
            card.classList.remove('enabled');
        }

        // Update local state
        const entity = this.currentEntities.get(entityId);
        if (entity) {
            entity.enabled = enabled;
        }

        // Update on server
        try {
            await fetch(`/api/backends/${this.currentBackendId}/entities/${entityId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });

            await this.updateStats();
        } catch (error) {
            console.error('Error updating entity:', error);
        }
    }

    // Update entity friendly name
    async updateEntityFriendlyName(entityId, friendlyName) {
        const entity = this.currentEntities.get(entityId);
        if (entity) {
            entity.friendly_name = friendlyName;
        }

        // Update on server
        try {
            await fetch(`/api/backends/${this.currentBackendId}/entities/${entityId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ friendly_name: friendlyName })
            });

            await this.updateStats();
        } catch (error) {
            console.error('Error updating entity:', error);
        }
    }

    // Show entity settings modal
    async showEntitySettings(button) {
        const card = button.closest('.entity-card');
        const entityId = card.dataset.entityId;
        const entity = this.currentEntities.get(entityId);

        if (!entity) return;

        const modal = document.getElementById('entitySettingsModal');
        if (!modal) return;

        // Set entity ID
        document.getElementById('entitySettingsId').textContent = entityId;
        document.getElementById('entityId').value = entityId;

        // Set friendly name
        document.getElementById('entityFriendlyName').value = entity.friendly_name || '';

        // Set aliases
        const aliasesContainer = document.getElementById('entityAliases');
        aliasesContainer.innerHTML = '';

        (entity.aliases || []).forEach(alias => {
            this.addAliasInput(alias);
        });

        // Set enabled state
        document.getElementById('entityEnabled').checked = entity.enabled || false;

        // Set priority
        document.getElementById('entityPriority').value = entity.priority || 5;

        // Set room override
        document.getElementById('entityRoom').value = entity.room || '';

        modal.style.display = 'block';
        modal.dataset.entityId = entityId;
    }

    // Close entity settings modal
    closeEntitySettingsModal() {
        const modal = document.getElementById('entitySettingsModal');
        if (modal) {
            modal.style.display = 'none';
        }
    }

    // Add alias input field
    addAliasInput(value = '') {
        const container = document.getElementById('entityAliases');
        if (!container) return;

        const group = document.createElement('div');
        group.className = 'alias-input-group';

        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-input alias-input';
        input.value = value;
        input.placeholder = 'Enter alias';

        const removeBtn = document.createElement('button');
        removeBtn.className = 'remove-alias-btn';
        removeBtn.textContent = 'Remove';
        removeBtn.onclick = () => group.remove();

        group.appendChild(input);
        group.appendChild(removeBtn);
        container.appendChild(group);
    }

    // Save entity settings
    async saveEntitySettings() {
        const modal = document.getElementById('entitySettingsModal');
        const entityId = modal.dataset.entityId;

        if (!entityId || !this.currentBackendId) return;

        const friendlyName = document.getElementById('entityFriendlyName').value;
        const enabled = document.getElementById('entityEnabled').checked;
        const priority = parseInt(document.getElementById('entityPriority').value);
        const room = document.getElementById('entityRoom').value;

        // Collect aliases
        const aliases = [];
        document.querySelectorAll('.alias-input').forEach(input => {
            if (input.value.trim()) {
                aliases.push(input.value.trim());
            }
        });

        // Update local state
        const entity = this.currentEntities.get(entityId);
        if (entity) {
            entity.friendly_name = friendlyName;
            entity.enabled = enabled;
            entity.aliases = aliases;
            entity.priority = priority;
            if (room) entity.room = room;
        }

        // Update on server
        try {
            await fetch(`/api/backends/${this.currentBackendId}/entities/${entityId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    friendly_name: friendlyName,
                    enabled: enabled,
                    aliases: aliases,
                    priority: priority
                })
            });

            this.closeEntitySettingsModal();
            this.renderEntities();
            await this.updateStats();
            this.showNotification('Entity settings saved successfully!', 'success');
        } catch (error) {
            console.error('Error saving entity settings:', error);
            this.showNotification('Error saving entity settings', 'error');
        }
    }

    // Select all entities
    selectAllEntities() {
        document.querySelectorAll('.entity-enable-checkbox').forEach(checkbox => {
            checkbox.checked = true;
            const card = checkbox.closest('.entity-card');
            if (card) {
                card.classList.add('enabled');
                const entityId = card.dataset.entityId;
                const entity = this.currentEntities.get(entityId);
                if (entity) {
                    entity.enabled = true;
                }
            }
        });

        this.bulkUpdateEntities(true);
    }

    // Clear all entities
    clearAllEntities() {
        document.querySelectorAll('.entity-enable-checkbox').forEach(checkbox => {
            checkbox.checked = false;
            const card = checkbox.closest('.entity-card');
            if (card) {
                card.classList.remove('enabled');
                const entityId = card.dataset.entityId;
                const entity = this.currentEntities.get(entityId);
                if (entity) {
                    entity.enabled = false;
                }
            }
        });

        this.bulkUpdateEntities(false);
    }

    // Bulk update entities
    async bulkUpdateEntities(enabled) {
        if (!this.currentBackendId) return;

        const entityIds = Array.from(this.currentEntities.keys());

        try {
            await fetch(`/api/backends/${this.currentBackendId}/entities/bulk`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    entity_ids: entityIds,
                    enabled: enabled
                })
            });

            await this.updateStats();
        } catch (error) {
            console.error('Error bulk updating entities:', error);
        }
    }

    // Save entity configuration
    async saveEntityConfig() {
        await this.loadBackends();
        this.closeEntityConfigModal();
        this.showNotification('Entity configuration saved successfully!', 'success');
    }

    // Filter entities based on search and type
    filterEntities() {
        const searchTerm = (document.getElementById('entitySearch')?.value || '').toLowerCase();
        const typeFilter = document.getElementById('entityTypeFilter')?.value || '';

        document.querySelectorAll('.entity-card').forEach(card => {
            const entityId = card.dataset.entityId;
            const entity = this.currentEntities.get(entityId);

            if (!entity) return;

            let visible = true;

            // Search filter
            if (searchTerm) {
                const searchString = `${entityId} ${entity.original_name} ${entity.friendly_name || ''}`.toLowerCase();
                visible = searchString.includes(searchTerm);
            }

            // Type filter
            if (visible && typeFilter) {
                visible = entity.domain === typeFilter;
            }

            card.style.display = visible ? '' : 'none';
        });
    }

    // Update entity statistics
    updateEntityStats(stats) {
        document.getElementById('totalEntities').textContent = stats.total_entities || 0;
        document.getElementById('enabledEntities').textContent = stats.enabled_entities || 0;
        document.getElementById('configuredEntities').textContent = stats.configured_entities || 0;
    }

    // Update statistics
    async updateStats() {
        if (!this.currentBackendId) return;

        try {
            const response = await fetch(`/api/backends/${this.currentBackendId}/entities/stats`);
            const stats = await response.json();
            this.updateEntityStats(stats);
        } catch (error) {
            console.error('Error updating stats:', error);
        }
    }

    // Delete backend
    async deleteBackend(button) {
        const card = button.closest('.backend-card');
        const backendId = card.dataset.backendId;
        const backend = this.backends.get(backendId);

        if (!backend) return;

        if (!confirm(`Are you sure you want to delete "${backend.name}"?`)) {
            return;
        }

        try {
            const response = await fetch(`/api/backends/${backendId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                await this.loadBackends();
                this.showNotification('Backend deleted successfully!', 'success');
            } else {
                throw new Error('Failed to delete backend');
            }
        } catch (error) {
            console.error('Error deleting backend:', error);
            this.showNotification('Error deleting backend', 'error');
        }
    }

    // Show status message
    showStatus(elementId, message, type) {
        const element = document.getElementById(elementId);
        if (element) {
            element.style.display = 'block';
            element.className = 'connection-status ' + type;
            element.textContent = message;

            if (type === 'success') {
                element.classList.add('success-animation');
            } else if (type === 'error') {
                element.classList.add('error-animation');
            }
        }
    }

    // Show notification
    showNotification(message, type) {
        // This could be enhanced with a proper notification system
        console.log(`[${type}] ${message}`);
    }
}

// Export for use in main admin.js
window.BackendManager = BackendManager;