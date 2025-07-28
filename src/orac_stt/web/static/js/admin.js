// ORAC STT Admin Dashboard JavaScript

class OracSTTAdmin {
    constructor() {
        this.ws = null;
        this.reconnectInterval = null;
        this.commands = new Map();
        this.maxCommands = 5;
        
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
    }
    
    async init() {
        // Load initial data
        await this.loadModels();
        await this.loadRecentCommands();
        
        // Set up WebSocket connection
        this.connectWebSocket();
        
        // Set up event listeners
        this.setupEventListeners();
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
            this.connectionText.textContent = 'Connected';
        } else {
            this.connectionStatus.classList.add('disconnected');
            this.connectionText.textContent = 'Disconnected';
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
            const response = await fetch('/admin/models');
            const models = await response.json();
            
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
            
        } catch (error) {
            console.error('Failed to load models:', error);
            this.modelDropdown.innerHTML = '<option>Error loading models</option>';
        }
    }
    
    async loadRecentCommands() {
        try {
            const response = await fetch('/admin/commands');
            const commands = await response.json();
            
            // Clear existing commands
            this.commands.clear();
            this.commandsGrid.innerHTML = '';
            
            // Add commands (they come newest first)
            commands.forEach(command => {
                this.addCommand(command, false);
            });
            
            this.updateEmptyState();
            
        } catch (error) {
            console.error('Failed to load commands:', error);
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
            alert(`Failed to switch model: ${error.message}`);
            
            // Revert dropdown to current model
            await this.loadModels();
            
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
        
        // Populate tile data
        tile.querySelector('.command-timestamp').textContent = this.formatTimestamp(command.timestamp);
        tile.querySelector('.command-confidence').textContent = `${(command.confidence * 100).toFixed(1)}%`;
        tile.querySelector('.command-text').textContent = command.text || '(empty)';
        tile.querySelector('.command-duration').textContent = `${command.duration.toFixed(1)}s`;
        
        // Set up audio player
        const audio = tile.querySelector('.command-audio');
        const playBtn = tile.querySelector('.play-btn');
        
        if (command.audio_path) {
            audio.src = `/admin/commands/${command.id}/audio`;
            
            playBtn.addEventListener('click', () => {
                if (audio.paused) {
                    // Stop all other audio
                    document.querySelectorAll('.command-audio').forEach(a => {
                        if (a !== audio) a.pause();
                    });
                    document.querySelectorAll('.play-btn').forEach(btn => {
                        btn.textContent = '▶ PLAY';
                    });
                    
                    audio.play();
                    playBtn.textContent = '⏸ PAUSE';
                } else {
                    audio.pause();
                    playBtn.textContent = '▶ PLAY';
                }
            });
            
            audio.addEventListener('ended', () => {
                playBtn.textContent = '▶ PLAY';
            });
            
            audio.addEventListener('error', () => {
                playBtn.textContent = '❌ ERROR';
                playBtn.disabled = true;
            });
        } else {
            playBtn.disabled = true;
            playBtn.textContent = 'NO AUDIO';
        }
        
        // Add to DOM
        if (isNew) {
            // Add flash animation for new commands
            tileElement.classList.add('new-command');
            this.commandsGrid.insertBefore(tile, this.commandsGrid.firstChild);
            
            // Remove animation class after animation completes
            setTimeout(() => {
                const el = document.querySelector(`[data-command-id="${command.id}"]`);
                if (el) el.classList.remove('new-command');
            }, 1000);
        } else {
            // Add to end for initial load
            this.commandsGrid.appendChild(tile);
        }
        
        // Store command
        this.commands.set(command.id, command);
        
        // Remove oldest command if we exceed max
        if (this.commands.size > this.maxCommands) {
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
        const now = new Date();
        const diff = now - date;
        
        // If less than 1 minute ago
        if (diff < 60000) {
            return 'Just now';
        }
        
        // If less than 1 hour ago
        if (diff < 3600000) {
            const minutes = Math.floor(diff / 60000);
            return `${minutes}m ago`;
        }
        
        // If today
        if (date.toDateString() === now.toDateString()) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
        
        // Otherwise show date and time
        return date.toLocaleString([], { 
            month: 'short', 
            day: 'numeric', 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.oracAdmin = new OracSTTAdmin();
});