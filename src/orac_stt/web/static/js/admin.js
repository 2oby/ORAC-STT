// ORAC STT Admin Dashboard JavaScript

class OracSTTAdmin {
    constructor() {
        this.ws = null;
        this.reconnectInterval = null;
        this.commands = new Map();
        this.maxCommands = 100; // Increased to show more commands
        this.cleanupInterval = null;
        
        // DOM elements
        this.connectionStatus = document.getElementById('connectionStatus');
        this.connectionText = document.getElementById('connectionText');
        this.currentModel = document.getElementById('currentModel');
        this.modelDropdown = document.getElementById('modelDropdown');
        this.commandsGrid = document.getElementById('commandsGrid');
        this.emptyState = document.getElementById('emptyState');
        this.commandTileTemplate = document.getElementById('commandTileTemplate');
        
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
        
        // Set up WebSocket connection
        this.connectWebSocket();
        
        // Set up event listeners
        this.setupEventListeners();
        
        // Start cleanup interval for old commands
        this.startCleanupInterval();
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
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
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
    
    showSettingsPopup() {
        // Get the machine's IP or hostname
        const host = window.location.hostname || 'localhost';
        const port = window.location.port || '7272';
        const webhookUrl = `http://${host}:${port}/stt/v1/stream`;
        
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
            <h3>API Information</h3>
            <p>Use this URL to send audio streams to ORAC STT:</p>
            <div class="webhook-url-container">
                <input type="text" class="webhook-url" value="${webhookUrl}" readonly>
                <button class="copy-btn" onclick="window.oracAdmin.copyWebhookUrl('${webhookUrl}', this)">COPY</button>
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
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.oracAdmin = new OracSTTAdmin();
});