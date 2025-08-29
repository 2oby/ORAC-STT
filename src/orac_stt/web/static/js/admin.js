// ORAC STT Admin Dashboard JavaScript

class OracSTTAdmin {
    constructor() {
        this.ws = null;
        this.reconnectInterval = null;
        this.commands = new Map();
        this.maxCommands = 100; // Increased to show more commands
        this.cleanupInterval = null;
        this.topics = new Map();
        this.topicRefreshInterval = null;
        this.currentTopicForSettings = null;
        
        // DOM elements
        this.connectionStatus = document.getElementById('connectionStatus');
        this.connectionText = document.getElementById('connectionText');
        this.currentModel = document.getElementById('currentModel');
        this.modelDropdown = document.getElementById('modelDropdown');
        this.commandsGrid = document.getElementById('commandsGrid');
        this.emptyState = document.getElementById('emptyState');
        this.commandTileTemplate = document.getElementById('commandTileTemplate');
        this.topicsContainer = document.getElementById('topicsContainer');
        this.topicCardTemplate = document.getElementById('topicCardTemplate');
        this.topicSettingsModal = document.getElementById('topicSettingsModal');
        
        // Initialize
        this.init();
        
        // Set up scrollbar
        this.setupScrollbar();
    }
    
    async init() {
        // Add mock data for demonstration
        this.addMockData();
        
        // Set initial disconnected state
        this.updateConnectionStatus(false);
        
        // Load initial data
        await this.loadModels();
        await this.loadRecentCommands();
        await this.loadTopics();
        
        // Set up WebSocket connection
        this.connectWebSocket();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Start cleanup interval for old commands
        this.startCleanupInterval();
        
        // Start topic refresh interval
        this.startTopicRefreshInterval();
    }
    
    setupScrollbar() {
        const scrollbarThumb = document.querySelector('.scrollbar-thumb');
        const scrollbarTrack = document.querySelector('.scrollbar-track');
        
        if (!scrollbarThumb || !scrollbarTrack) return;
        
        const updateScrollbar = () => {
            const windowHeight = window.innerHeight;
            const scrollHeight = document.body.scrollHeight;
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            
            // Only show scrollbar if content is taller than viewport
            if (scrollHeight <= windowHeight + 10) { // Adding small buffer
                scrollbarTrack.style.display = 'none';
                return;
            }
            
            scrollbarTrack.style.display = 'block';
            
            const trackHeight = scrollbarTrack.offsetHeight;
            const thumbHeight = Math.max(30, (windowHeight / scrollHeight) * trackHeight);
            const maxThumbTop = trackHeight - thumbHeight;
            const thumbTop = (scrollTop / (scrollHeight - windowHeight)) * maxThumbTop;
            
            scrollbarThumb.style.height = thumbHeight + 'px';
            scrollbarThumb.style.top = Math.min(Math.max(0, thumbTop), maxThumbTop) + 'px';
        };
        
        // Update scrollbar on various events
        window.addEventListener('scroll', updateScrollbar);
        window.addEventListener('resize', updateScrollbar);
        
        // Also update when commands are added/removed
        const observer = new MutationObserver(updateScrollbar);
        observer.observe(this.commandsGrid, { childList: true });
        
        // Initial update
        setTimeout(updateScrollbar, 100);
    }
    
    addMockData() {
        // Add sample commands matching the mockup
        const mockCommands = [
            {
                id: 'mock1',
                timestamp: new Date(Date.now() - 10000).toISOString(),
                confidence: 0.95,
                text: "Hey computer, the bird flyer is high in the sun.",
                duration: 3.5,
                audio_path: null,
                hasError: true
            },
            {
                id: 'mock2',
                timestamp: new Date(Date.now() - 20000).toISOString(),
                confidence: 0.95,
                text: "A computer wears the kitchen.",
                duration: 2.3,
                audio_path: true
            },
            {
                id: 'mock3',
                timestamp: new Date(Date.now() - 30000).toISOString(),
                confidence: 0.95,
                text: "Hey computer.",
                duration: 6.0,
                audio_path: true
            },
            {
                id: 'mock4',
                timestamp: new Date(Date.now() - 40000).toISOString(),
                confidence: 0.95,
                text: "Hey computer, turn on the bedroom lights.",
                duration: 3.4,
                audio_path: true
            },
            {
                id: 'mock5',
                timestamp: new Date(Date.now() - 50000).toISOString(),
                confidence: 0.95,
                text: "Hey computer, turn on the bedroom lights.",
                duration: 3.4,
                audio_path: true
            }
        ];
        
        // Don't add mock commands automatically - wait for real data
        // Comment out for production
        /*
        setTimeout(() => {
            mockCommands.reverse().forEach((cmd, index) => {
                setTimeout(() => {
                    this.addCommand(cmd, false);
                }, index * 100);
            });
        }, 500);
        */
    }
    
    setupEventListeners() {
        // Model selector
        this.modelDropdown.addEventListener('change', async (e) => {
            const selectedModel = e.target.value;
            if (selectedModel) {
                await this.selectModel(selectedModel);
            }
        });
        
        // Page visibility change
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                this.disconnect();
            } else {
                this.connectWebSocket();
            }
        });
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/admin/ws`;
        
        console.log('Connecting to WebSocket:', wsUrl);
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus(true);
            
            // Clear any reconnect interval
            if (this.reconnectInterval) {
                clearInterval(this.reconnectInterval);
                this.reconnectInterval = null;
            }
        };
        
        this.ws.onmessage = (event) => {
            // Handle ping/pong messages
            if (event.data === 'pong') {
                // Ignore pong messages
                return;
            }
            
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('Failed to parse WebSocket message:', event.data, error);
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus(false);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus(false);
            
            // Attempt to reconnect
            if (!this.reconnectInterval) {
                this.reconnectInterval = setInterval(() => {
                    console.log('Attempting to reconnect...');
                    this.connectWebSocket();
                }, 5000);
            }
        };
        
        // Send ping every 30 seconds to keep connection alive
        setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send('ping');
            }
        }, 30000);
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
    
    updateConnectionStatus(connected) {
        if (connected) {
            this.connectionStatus.classList.remove('disconnected');
            this.connectionText.textContent = 'Dashboard Connected';
        } else {
            this.connectionStatus.classList.add('disconnected');
            this.connectionText.textContent = 'Dashboard Disconnected';
        }
    }
    
    handleWebSocketMessage(data) {
        console.log('WebSocket message:', data);
        
        switch (data.type) {
            case 'connected':
                console.log('Server acknowledged connection');
                break;
                
            case 'new_command':
                this.addCommand(data.command, true);
                break;
                
            case 'model_changed':
                this.currentModel.textContent = data.model;
                this.modelDropdown.value = data.model;
                break;
                
            default:
                console.warn('Unknown message type:', data.type);
        }
    }
    
    async loadModels() {
        try {
            // Set mock models
            const models = [
                { name: 'whisper-tiny', description: 'Fastest inference, basic accuracy', current: false },
                { name: 'whisper-small', description: 'Better accuracy, slower', current: true },
                { name: 'whisper-medium', description: 'Best accuracy, slowest', current: false }
            ];
            
            // Clear dropdown
            this.modelDropdown.innerHTML = '';
            
            // Populate dropdown
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.name;
                option.textContent = `${model.name} - ${model.description}`;
                
                if (model.current) {
                    option.selected = true;
                    this.currentModel.textContent = model.name;
                }
                
                this.modelDropdown.appendChild(option);
            });
            
            this.modelDropdown.disabled = false;
            
            // Try real API
            const response = await fetch('/admin/models').catch(() => ({ ok: false }));
            if (response.ok) {
                const apiModels = await response.json();
                // Update with real data if available
                this.modelDropdown.innerHTML = '';
                apiModels.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.name;
                    option.textContent = `${model.name} - ${model.description}`;
                    
                    if (model.current) {
                        option.selected = true;
                        this.currentModel.textContent = model.name;
                    }
                    
                    this.modelDropdown.appendChild(option);
                });
            }
            
        } catch (error) {
            console.error('Failed to load models:', error);
            // Keep mock data
        }
    }
    
    async loadRecentCommands() {
        try {
            const response = await fetch('/admin/commands').catch(() => ({ ok: false }));
            if (response.ok) {
                const commands = await response.json();
                
                // Clear existing non-mock commands
                Array.from(this.commands.keys()).forEach(id => {
                    if (!id.startsWith('mock')) {
                        this.removeCommand(id);
                    }
                });
                
                // Add real commands
                commands.forEach(command => {
                    this.addCommand(command, false);
                });
            }
            
            this.updateEmptyState();
            
        } catch (error) {
            console.error('Failed to load commands:', error);
            // Keep mock data
        }
    }
    
    async selectModel(modelName) {
        this.modelDropdown.disabled = true;
        
        try {
            const response = await fetch('/admin/models/select', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ model_name: modelName })
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.currentModel.textContent = modelName;
                console.log('Model switched successfully:', result.message);
            } else {
                throw new Error(result.detail || 'Failed to switch model');
            }
            
        } catch (error) {
            console.error('Failed to switch model:', error);
            // Don't show alert for demo
            this.currentModel.textContent = modelName;
            
        } finally {
            this.modelDropdown.disabled = false;
        }
    }
    
    addCommand(command, isNew = false) {
        // Check if command already exists
        if (this.commands.has(command.id)) {
            return;
        }
        
        // Create tile from template
        const tile = this.commandTileTemplate.content.cloneNode(true);
        const tileElement = tile.querySelector('.command-tile');
        
        // Set command ID
        tileElement.dataset.commandId = command.id;
        
        // Add error class if needed
        if (command.hasError) {
            tileElement.classList.add('error');
        }
        
        // Populate tile data
        tile.querySelector('.command-timestamp').textContent = this.formatTimestamp(command.timestamp);
        tile.querySelector('.command-confidence').textContent = `${(command.confidence * 100).toFixed(1)}%`;
        tile.querySelector('.command-text').textContent = command.text || '(empty)';
        tile.querySelector('.command-duration').textContent = `${command.duration.toFixed(1)}s`;
        
        // Set up audio player
        const audio = tile.querySelector('.command-audio');
        const playBtn = tile.querySelector('.play-btn');
        const errorBtn = tile.querySelector('.error-btn');
        
        if (command.hasError) {
            playBtn.style.display = 'none';
            errorBtn.style.display = 'inline-block';
        } else if (command.audio_path) {
            audio.src = `/admin/commands/${command.id}/audio`;
            
            playBtn.addEventListener('click', () => {
                if (audio.paused) {
                    // Stop all other audio
                    document.querySelectorAll('.command-audio').forEach(a => {
                        if (a !== audio) a.pause();
                    });
                    document.querySelectorAll('.play-btn').forEach(btn => {
                        btn.textContent = '▶ PLAY';
                        btn.dataset.state = 'play';
                    });
                    
                    audio.play();
                    playBtn.textContent = '⏸ PAUSE';
                    playBtn.dataset.state = 'playing';
                } else {
                    audio.pause();
                    playBtn.textContent = '▶ PLAY';
                    playBtn.dataset.state = 'play';
                }
            });
            
            audio.addEventListener('ended', () => {
                playBtn.textContent = '▶ PLAY';
                playBtn.dataset.state = 'play';
            });
            
            audio.addEventListener('error', () => {
                // For demo, just ignore audio errors
                console.log('Audio error (expected in demo)');
            });
        } else {
            playBtn.disabled = true;
            playBtn.textContent = 'NO AUDIO';
        }
        
        // Add to DOM
        this.commandsGrid.insertBefore(tile, this.commandsGrid.firstChild);
        
        // Store command with timestamp
        this.commands.set(command.id, {
            ...command,
            timestamp: command.timestamp || new Date().toISOString()
        });
        
        // Remove oldest commands if we exceed max
        while (this.commands.size > this.maxCommands) {
            const oldestId = Array.from(this.commands.keys())[this.commands.size - 1];
            this.removeCommand(oldestId);
        }
        
        this.updateEmptyState();
    }
    
    removeCommand(commandId) {
        const tile = document.querySelector(`[data-command-id="${commandId}"]`);
        if (tile) {
            tile.remove();
        }
        this.commands.delete(commandId);
    }
    
    updateEmptyState() {
        if (this.commands.size === 0) {
            this.emptyState.style.display = 'block';
            this.commandsGrid.style.display = 'none';
        } else {
            this.emptyState.style.display = 'none';
            this.commandsGrid.style.display = 'grid';
        }
    }
    
    formatTimestamp(isoString) {
        const date = new Date(isoString);
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        return `${hours}:${minutes}`;
    }
    
    startCleanupInterval() {
        // Clean up commands older than 6 hours every minute
        this.cleanupInterval = setInterval(() => {
            this.cleanupOldCommands();
        }, 60000); // Check every minute
        
        // Initial cleanup
        this.cleanupOldCommands();
    }
    
    cleanupOldCommands() {
        const sixHoursAgo = Date.now() - (6 * 60 * 60 * 1000); // 6 hours in milliseconds
        const commandsToRemove = [];
        
        this.commands.forEach((command, id) => {
            const commandTime = new Date(command.timestamp).getTime();
            if (commandTime < sixHoursAgo) {
                commandsToRemove.push(id);
            }
        });
        
        // Remove old commands
        commandsToRemove.forEach(id => {
            console.log(`Removing old command: ${id}`);
            this.removeCommand(id);
        });
        
        if (commandsToRemove.length > 0) {
            console.log(`Cleaned up ${commandsToRemove.length} old commands`);
            this.updateEmptyState();
        }
    }
    
    async showSettingsPopup() {
        // Get the machine's IP or hostname
        const host = window.location.hostname || 'localhost';
        const port = window.location.port || '7272';
        const webhookUrl = `http://${host}:${port}/stt/v1/stream`;
        
        // Load current ORAC Core config
        let oracCoreConfig = { url: 'http://192.168.8.191:8000', timeout: 30 };
        try {
            const response = await fetch('/admin/config/orac-core');
            if (response.ok) {
                oracCoreConfig = await response.json();
            }
        } catch (error) {
            console.error('Failed to load ORAC Core config:', error);
        }
        
        // Create popup overlay
        const overlay = document.createElement('div');
        overlay.className = 'settings-overlay';
        overlay.onclick = (e) => {
            if (e.target === overlay) {
                overlay.remove();
            }
        };
        
        // Create popup content
        const popup = document.createElement('div');
        popup.className = 'settings-popup';
        popup.innerHTML = `
            <h3>Configuration</h3>
            
            <!-- ORAC STT Webhook URL Section -->
            <div class="config-section">
                <h4>ORAC STT Webhook URL</h4>
                <p>Use this URL in Hey ORAC wake word settings:</p>
                <div class="webhook-url-container">
                    <input type="text" class="webhook-url" value="${webhookUrl}" readonly>
                    <button class="copy-btn" onclick="window.oracAdmin.copyWebhookUrl('${webhookUrl}', this)">COPY</button>
                </div>
            </div>
            
            <!-- ORAC Core Configuration Section -->
            <div class="config-section">
                <h4>ORAC Core Target URL</h4>
                <p>Configure where transcriptions are sent:</p>
                <div class="orac-core-config">
                    <div class="input-group">
                        <input type="text" id="oracCoreUrl" class="config-input" value="${oracCoreConfig.url}" placeholder="http://192.168.8.191:8000">
                        <button class="test-btn" onclick="window.oracAdmin.testOracCoreConnection()">TEST</button>
                    </div>
                    <div class="config-status" id="oracCoreStatus"></div>
                    <button class="save-btn" onclick="window.oracAdmin.saveOracCoreConfig()">SAVE CONFIG</button>
                </div>
            </div>
            
            <button class="close-btn" onclick="this.closest('.settings-overlay').remove()">CLOSE</button>
        `;
        
        overlay.appendChild(popup);
        document.body.appendChild(overlay);
    }
    
    copyWebhookUrl(url, button) {
        navigator.clipboard.writeText(url).then(() => {
            const originalText = button.textContent;
            button.textContent = 'COPIED!';
            button.classList.add('copied');
            
            setTimeout(() => {
                button.textContent = originalText;
                button.classList.remove('copied');
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy URL:', err);
            // Fallback: select the input
            const input = button.previousElementSibling;
            input.select();
            document.execCommand('copy');
        });
    }
    
    async testOracCoreConnection() {
        const statusDiv = document.getElementById('oracCoreStatus');
        const testBtn = document.querySelector('.test-btn');
        
        // Show loading state
        statusDiv.innerHTML = '<span class="status-loading">Testing connection...</span>';
        testBtn.disabled = true;
        testBtn.textContent = 'TESTING...';
        
        try {
            const response = await fetch('/admin/config/orac-core/test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                statusDiv.innerHTML = `<span class="status-success">✓ ${result.message}</span>`;
            } else {
                statusDiv.innerHTML = `<span class="status-error">✗ ${result.message}</span>`;
            }
        } catch (error) {
            statusDiv.innerHTML = `<span class="status-error">✗ Connection test failed: ${error.message}</span>`;
        } finally {
            testBtn.disabled = false;
            testBtn.textContent = 'TEST';
        }
    }
    
    async saveOracCoreConfig() {
        const urlInput = document.getElementById('oracCoreUrl');
        const statusDiv = document.getElementById('oracCoreStatus');
        const saveBtn = document.querySelector('.save-btn');
        
        const url = urlInput.value.trim();
        if (!url) {
            statusDiv.innerHTML = '<span class="status-error">✗ Please enter a URL</span>';
            return;
        }
        
        // Show loading state
        statusDiv.innerHTML = '<span class="status-loading">Saving configuration...</span>';
        saveBtn.disabled = true;
        saveBtn.textContent = 'SAVING...';
        
        try {
            const response = await fetch('/admin/config/orac-core', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    url: url,
                    timeout: 30
                })
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                statusDiv.innerHTML = `<span class="status-success">✓ ${result.message}</span>`;
            } else if (result.status === 'warning') {
                statusDiv.innerHTML = `<span class="status-warning">⚠ ${result.message}</span>`;
            } else {
                statusDiv.innerHTML = `<span class="status-error">✗ ${result.message}</span>`;
            }
        } catch (error) {
            statusDiv.innerHTML = `<span class="status-error">✗ Failed to save configuration: ${error.message}</span>`;
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = 'SAVE CONFIG';
        }
    }
    
    // Topic Management Methods
    async loadTopics() {
        try {
            const response = await fetch('/admin/topics');
            if (!response.ok) throw new Error('Failed to load topics');
            
            const topics = await response.json();
            this.renderTopics(topics);
        } catch (error) {
            console.error('Error loading topics:', error);
        }
    }
    
    renderTopics(topics) {
        // Check if container exists
        if (!this.topicsContainer) {
            console.error('Topics container not found');
            return;
        }
        
        if (!topics || topics.length === 0) {
            console.log('No topics to display');
            this.topicsContainer.innerHTML = '';
            this.topics.clear();
            return;
        }
        
        console.log(`Rendering ${topics.length} topics`);
        
        // Sort topics by activity (active first)
        topics.sort((a, b) => {
            if (a.is_active && !b.is_active) return -1;
            if (!a.is_active && b.is_active) return 1;
            return 0;
        });
        
        // Track which topics we've seen
        const seenTopics = new Set();
        
        // Update existing cards or create new ones
        topics.forEach(topic => {
            seenTopics.add(topic.name);
            const existingCard = document.querySelector(`[data-topic-name="${topic.name}"]`);
            
            if (existingCard) {
                // Update existing card
                this.updateTopicCard(existingCard, topic);
                // Add pulse animation with proper cleanup
                if (!existingCard.classList.contains('refreshing')) {
                    existingCard.classList.add('refreshing');
                    // Remove class after animation completes (2s duration)
                    setTimeout(() => {
                        existingCard.classList.remove('refreshing');
                    }, 2000);
                }
            } else {
                // Create new card
                const card = this.createTopicCard(topic);
                this.topicsContainer.appendChild(card);
            }
            
            this.topics.set(topic.name, topic);
        });
        
        // Remove cards for topics that no longer exist
        document.querySelectorAll('.topic-card').forEach(card => {
            const topicName = card.dataset.topicName;
            if (!seenTopics.has(topicName)) {
                card.style.animation = 'fadeOut 0.5s ease-out';
                setTimeout(() => {
                    card.remove();
                    this.topics.delete(topicName);
                }, 500);
            }
        });
    }
    
    updateTopicCard(card, topic) {
        // Update status dot
        const statusDot = card.querySelector('.topic-status-dot');
        if (statusDot) {
            // Only update if status changed
            const wasActive = statusDot.classList.contains('active');
            const wasDormant = statusDot.classList.contains('dormant');
            const wasStale = statusDot.classList.contains('stale');
            
            statusDot.classList.remove('active', 'dormant', 'stale');
            
            if (topic.is_active) {
                statusDot.classList.add('active');
            } else {
                // Check if stale (more than 120 seconds)
                const lastSeen = new Date(topic.last_seen);
                const now = new Date();
                const secondsSinceLastSeen = (now - lastSeen) / 1000;
                
                if (secondsSinceLastSeen > 120) {
                    statusDot.classList.add('stale');
                } else {
                    statusDot.classList.add('dormant');
                }
            }
        }
        
        // Update card classes without resetting all classes
        const isRefreshing = card.classList.contains('refreshing');
        card.classList.remove('dormant', 'stale');
        
        if (!topic.is_active) {
            const lastSeen = new Date(topic.last_seen);
            const now = new Date();
            const secondsSinceLastSeen = (now - lastSeen) / 1000;
            
            if (secondsSinceLastSeen > 120) {
                card.classList.add('stale');
            } else {
                card.classList.add('dormant');
            }
        }
        
        // Preserve refreshing class if it's still animating
        if (isRefreshing) {
            card.classList.add('refreshing');
        }
        
        // Update activity text
        const activityEl = card.querySelector('.topic-activity');
        if (activityEl) {
            if (topic.last_seen) {
                const lastSeen = new Date(topic.last_seen);
                const now = new Date();
                const diffMs = now - lastSeen;
                const diffMins = Math.floor(diffMs / 60000);
                
                if (diffMins < 1) {
                    activityEl.textContent = 'Just now';
                } else if (diffMins < 60) {
                    activityEl.textContent = `${diffMins}m ago`;
                } else {
                    const diffHours = Math.floor(diffMins / 60);
                    activityEl.textContent = `${diffHours}h ago`;
                }
            } else {
                activityEl.textContent = 'Never';
            }
        }
    }
    
    createTopicCard(topic) {
        if (!this.topicCardTemplate) {
            console.error('Topic card template not found');
            return document.createElement('div');
        }
        
        const template = this.topicCardTemplate.content.cloneNode(true);
        const card = template.querySelector('.topic-card');
        
        card.dataset.topicName = topic.name;
        
        // Set status (active or dormant)
        if (!topic.is_active) {
            card.classList.add('dormant');
        }
        
        // Set topic name
        const nameEl = card.querySelector('.topic-name');
        nameEl.textContent = topic.name;
        
        // Set activity info
        const activityEl = card.querySelector('.topic-activity');
        if (topic.last_seen) {
            const lastSeen = new Date(topic.last_seen);
            const now = new Date();
            const diffMs = now - lastSeen;
            const diffMins = Math.floor(diffMs / 60000);
            
            if (diffMins < 1) {
                activityEl.textContent = 'Just now';
            } else if (diffMins < 60) {
                activityEl.textContent = `${diffMins}m ago`;
            } else {
                const diffHours = Math.floor(diffMins / 60);
                activityEl.textContent = `${diffHours}h ago`;
            }
        } else {
            activityEl.textContent = 'Never';
        }
        
        // Set up settings button
        const settingsBtn = card.querySelector('.topic-settings-btn');
        settingsBtn.addEventListener('click', () => {
            this.openTopicSettings(topic.name);
        });
        
        return card;
    }
    
    openTopicSettings(topicName) {
        const topic = this.topics.get(topicName);
        if (!topic) return;
        
        this.currentTopicForSettings = topicName;
        
        // Populate modal fields
        document.getElementById('topicNameField').value = topicName;
        const coreUrlField = document.getElementById('topicCoreUrlField');
        const useDefaultCheckbox = document.getElementById('useDefaultCheckbox');
        
        if (topic.orac_core_url) {
            coreUrlField.value = topic.orac_core_url;
            useDefaultCheckbox.checked = false;
            coreUrlField.disabled = false;
        } else {
            coreUrlField.value = '';
            useDefaultCheckbox.checked = true;
            coreUrlField.disabled = true;
        }
        
        // Set up checkbox listener
        useDefaultCheckbox.onchange = (e) => {
            coreUrlField.disabled = e.target.checked;
            if (e.target.checked) {
                coreUrlField.value = '';
            }
        };
        
        // Show modal
        this.topicSettingsModal.style.display = 'block';
    }
    
    closeTopicSettings() {
        this.topicSettingsModal.style.display = 'none';
        this.currentTopicForSettings = null;
    }
    
    async deleteTopic() {
        if (!this.currentTopicForSettings) return;
        
        const topicName = this.currentTopicForSettings.name;
        
        // Confirm deletion
        if (!confirm(`Are you sure you want to delete the topic "${topicName}"?\n\nThis action cannot be undone.`)) {
            return;
        }
        
        try {
            const response = await fetch(`/admin/topics/${encodeURIComponent(topicName)}`, {
                method: 'DELETE'
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to delete topic');
            }
            
            // Reload topics to reflect changes
            await this.loadTopics();
            
            // Close modal
            this.closeTopicSettings();
            
            // Show success message (optional)
            console.log(`Topic "${topicName}" deleted successfully`);
        } catch (error) {
            console.error('Error deleting topic:', error);
            alert('Failed to delete topic: ' + error.message);
        }
    }
    
    async saveTopicSettings() {
        if (!this.currentTopicForSettings) return;
        
        const coreUrlField = document.getElementById('topicCoreUrlField');
        const useDefaultCheckbox = document.getElementById('useDefaultCheckbox');
        
        const coreUrl = useDefaultCheckbox.checked ? null : coreUrlField.value.trim() || null;
        
        try {
            const response = await fetch(`/admin/topics/${this.currentTopicForSettings}/config`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    orac_core_url: coreUrl
                })
            });
            
            if (!response.ok) throw new Error('Failed to save topic settings');
            
            // Reload topics to reflect changes
            await this.loadTopics();
            
            // Close modal
            this.closeTopicSettings();
        } catch (error) {
            console.error('Error saving topic settings:', error);
            alert('Failed to save topic settings: ' + error.message);
        }
    }
    
    async testTopicConnection() {
        const coreUrlField = document.getElementById('topicCoreUrlField');
        const url = coreUrlField.value.trim();
        
        if (!url) {
            alert('Please enter a Core URL to test');
            return;
        }
        
        try {
            // Simple connectivity test
            const response = await fetch(url + '/health', {
                method: 'GET',
                mode: 'no-cors' // Allow testing without CORS issues
            });
            
            alert('Connection test initiated. Check the Core URL logs for confirmation.');
        } catch (error) {
            alert('Connection test failed: ' + error.message);
        }
    }
    
    startTopicRefreshInterval() {
        // Refresh topics every 10 seconds
        this.topicRefreshInterval = setInterval(() => {
            this.loadTopics();
        }, 10000);
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.oracAdmin = new OracSTTAdmin();
});