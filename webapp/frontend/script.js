/**
 * antrikshGPT - Interactive Space Exploration Webapp
 * Advanced JavaScript for real-time space data and AI chat integration
 */

class AntrikshGPT {
    constructor() {
        this.ws = null;
        this.chatHistory = [];
        this.isConnected = false;
        this.retryCount = 0;
        this.maxRetries = 5;
        this.updateIntervals = {};
        this.activeToolCalls = new Map();
        this.toolCallHistory = [];
        
        this.init();
    }

    /**
     * Initialize the application
     */
    async init() {
        console.log('🚀 Initializing antrikshGPT...');
        
        // Show loading overlay
        this.showLoadingOverlay();
        
        // Initialize components
        await this.setupEventListeners();
        await this.connectWebSocket();
        await this.loadInitialData();
        this.initializeCopyButtons();
        
        // Hide loading overlay quickly
        setTimeout(() => {
            this.hideLoadingOverlay();
        }, 500);
        
        console.log('✨ antrikshGPT initialized successfully!');
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        const chatInput = document.getElementById('chat-input');
        const sendButton = document.getElementById('send-button');
        const charCounter = document.getElementById('char-counter');
        const clearChatButton = document.getElementById('clear-chat-button');
        const chatMessages = document.getElementById('chat-messages');
        const scrollBottomBtn = document.getElementById('scroll-bottom');

        if (clearChatButton) {
            clearChatButton.addEventListener('click', () => this.clearChat());
        }

        if (chatInput && sendButton && charCounter) {
            chatInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });

            chatInput.addEventListener('input', () => {
                // Auto-resize textarea
                chatInput.style.height = 'auto';
                chatInput.style.height = `${chatInput.scrollHeight}px`;

                // Update char counter
                const remaining = chatInput.maxLength - chatInput.value.length;
                charCounter.textContent = remaining;
                charCounter.style.color = remaining < 50 ? 'var(--space-pink)' : 'var(--space-gray)';
            });
            
            sendButton.addEventListener('click', () => {
                this.sendMessage();
            });
        }
        
        // Suggestion chips
        document.querySelectorAll('.suggestion-chip').forEach(chip => {
            chip.addEventListener('click', (e) => {
                const query = e.target.dataset.query;
                if (query) {
                    const chatInput = document.getElementById('chat-input');
                    chatInput.value = query;
                    chatInput.focus();
                    // Trigger input event to update character counter
                    chatInput.dispatchEvent(new Event('input'));
                }
            });
        });
        
        // Window events
        window.addEventListener('beforeunload', () => {
            if (this.ws) {
                this.ws.close();
            }
        });
        
        // Auto-refresh data every 30 seconds
        this.setupAutoRefresh();
        
        // Add demo tool call functionality (Ctrl+T for testing)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 't') {
                e.preventDefault();
                this.demoToolCall();
            }
        });

        // Scroll to bottom button visibility
        if (chatMessages && scrollBottomBtn) {
            const toggleScrollBtn = () => {
                const nearBottom = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight < 80;
                if (nearBottom) {
                    scrollBottomBtn.classList.remove('show');
                } else {
                    scrollBottomBtn.classList.add('show');
                }
            };

            chatMessages.addEventListener('scroll', toggleScrollBtn);
            scrollBottomBtn.addEventListener('click', () => {
                chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
            });

            // Initial state
            toggleScrollBtn();
        }
    }

    /**
     * Setup automatic data refresh (production-safe)
     */
    setupAutoRefresh() {
        // ISS location updates every 2 minutes (production-safe)
        this.updateIntervals.iss = setInterval(() => {
            this.loadISSData();
        }, 120000);
        
        // Next launch every 30 minutes (very conservative)
        this.updateIntervals.launch = setInterval(() => {
            this.loadNextLaunch();
        }, 1800000);

        // Space News every 30 minutes
        this.updateIntervals.spaceNews = setInterval(() => {
            this.loadSpaceNews();
        }, 1800000);

        // NEO data every 4 hours
        this.updateIntervals.neo = setInterval(() => {
            this.loadNEOData();
        }, 14400000);
        
        // Update time display every second
        this.updateIntervals.time = setInterval(() => {
            this.updateTimeDisplay();
        }, 1000);
        
        // Log refresh schedule for debugging
        console.log('📅 Refresh schedule: ISS every 2min, Launch every 30min');
    }

    /**
     * Connect to WebSocket for real-time updates
     */
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        console.log(`Connecting to WebSocket: ${wsUrl}`);
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('🔗 WebSocket connected');
            this.isConnected = true;
            this.retryCount = 0;
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
        
        this.ws.onclose = () => {
            console.log('🔌 WebSocket disconnected');
            this.isConnected = false;
            this.attemptReconnect();
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    /**
     * Handle WebSocket messages
     */
    handleWebSocketMessage(data) {
        console.log('📨 WebSocket message received:', data.type, data);
        
        switch (data.type) {
            case 'welcome':
                console.log('Welcome message:', data.message);
                break;
                
            case 'iss_update':
                const isCached = data.cached || data.data.cached;
                this.updateISSWidget(data.data, isCached);
                break;
            
            case 'chat_response':
                this.addMessageToChat(data.message, 'assistant');
                break;
                
            case 'chat_response_chunk':
                this.appendMessageChunk(data.chunk);
                break;
            
            case 'chat_response_end':
                this.finalizeMessage();
                break;
            
            case 'tool_call_event':
                this.handleToolCallEvent(data.event); // Correctly access nested event data
                break;
                
            case 'error':
                console.error('WebSocket error:', data.message);
                this.showNotification('Connection error: ' + data.message, 'error');
                break;
                
            default:
                console.log('Unhandled message type:', data.type);
        }
    }

    /**
     * Attempt to reconnect WebSocket
     */
    attemptReconnect() {
        if (this.retryCount < this.maxRetries) {
            this.retryCount++;
            const delay = Math.min(1000 * Math.pow(2, this.retryCount), 30000);
            
            console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.retryCount}/${this.maxRetries})`);
            
            setTimeout(() => {
                this.connectWebSocket();
            }, delay);
        } else {
            console.error('Max reconnection attempts reached');
            this.showNotification('Connection lost. Please refresh the page.', 'error');
        }
    }

    /**
     * Handle real tool call events from backend
     */
    handleToolCallEvent(event) {
        if (!event) {
            console.error('❌ Received a null or undefined tool call event');
            return;
        }

        console.log('🔧 Tool call event received from backend:', event);
        
        if (event.type === 'tool_call_start') {
            console.log(`📥 Starting tool call: ${event.tool_name} (ID: ${event.tool_id})`);
            const toolCallId = this.startToolCall(
                event.tool_name, 
                event.description || `Executing ${event.tool_name}`, 
                event.tool_id
            );
        } else if (event.type === 'tool_call_complete') {
            console.log(`📥 Completing tool call: ${event.tool_name} (ID: ${event.tool_id})`);
            this.completeToolCall(event.tool_id, event.result || event.error);
        } else {
            console.warn('🔧 Unknown tool call event type:', event.type);
        }
    }

    /**
     * Tool Call Management Methods
     */
    
    /**
     * Start tracking a tool call
     */
    startToolCall(toolName, description, id = null) {
        const toolCallId = id || `tool_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        // Check if this tool call already exists (in case of duplicate events)
        if (this.activeToolCalls.has(toolCallId)) {
            console.log(`🔧 Tool call ${toolName} already exists, skipping duplicate start event`);
            return toolCallId;
        }
        
        const toolCall = {
            id: toolCallId,
            name: toolName,
            description: description,
            startTime: Date.now(),
            status: 'active'
        };
        
        console.log(`🔧 Starting tool call: ${toolName} (ID: ${toolCallId})`);
        this.activeToolCalls.set(toolCallId, toolCall);
        console.log('🗺️ Map after add:', new Map(this.activeToolCalls));
        this.updateToolCallWidget();
        
        return toolCallId;
    }
    
    /**
     * Complete a tool call
     */
    completeToolCall(toolCallId, result = null) {
        const toolCall = this.activeToolCalls.get(toolCallId);
        console.log(`🔍 Completing tool call for ID: ${toolCallId}. Found tool:`, toolCall);

        if (toolCall && toolCall.status !== 'completed') { // Prevent multiple completions
            toolCall.status = 'completed';
            toolCall.endTime = Date.now();
            toolCall.duration = toolCall.endTime - toolCall.startTime;
            toolCall.result = result;
            
            this.updateToolCallWidget(); // Re-render to show completed state
            
            console.log(`✅ Completed tool call: ${toolCall.name} (${toolCall.duration}ms)`);
            
            // Remove from display after a delay
            setTimeout(() => {
                const itemEl = document.querySelector(`.tool-call-item[data-id="${toolCallId}"]`);
                if (itemEl) {
                    itemEl.style.animation = 'tool-call-item-exit 0.5s ease forwards';
                    
                    itemEl.addEventListener('animationend', () => {
                        if (this.activeToolCalls.has(toolCallId)) {
                            // Move to history
                            this.toolCallHistory.push(this.activeToolCalls.get(toolCallId));
                            this.activeToolCalls.delete(toolCallId);
                            console.log('🗺️ Map after delete:', new Map(this.activeToolCalls));
                            
                            // Keep only last 10 in history
                            if (this.toolCallHistory.length > 10) {
                                this.toolCallHistory = this.toolCallHistory.slice(-10);
                            }
                            
                            this.updateToolCallWidget(); // Re-render to remove the item
                        }
                    });
                } else {
                     // Fallback if element not found
                    if (this.activeToolCalls.has(toolCallId)) {
                        this.activeToolCalls.delete(toolCallId);
                        this.updateToolCallWidget();
                    }
                }
            }, 2000); // Keep completed item on screen for 2 seconds
        }
    }
    
    /**
     * Update the tool call widget display
     */
    updateToolCallWidget() {
        const widget = document.querySelector('.tool-call-widget');
        const status = document.getElementById('tool-call-status');
        const content = document.getElementById('tool-call-content');
        
        if (!widget || !status || !content) {
            console.error('Tool call widget DOM elements not found!');
            return;
        }
        
        const hasActiveCalls = this.activeToolCalls.size > 0;
        console.log(`📊 Updating widget. Has active calls: ${hasActiveCalls}. Calls:`, new Map(this.activeToolCalls));
        
        // Update widget state
        if (hasActiveCalls) {
            widget.classList.add('active');
            status.className = 'tool-call-status active';
        } else {
            widget.classList.remove('active');
            status.className = 'tool-call-status idle';
        }
        
        // Update content
        if (hasActiveCalls) {
            const activeCallsHtml = Array.from(this.activeToolCalls.values()).map(toolCall => {
                const isCompleted = toolCall.status === 'completed';
                const completedClass = isCompleted ? 'completed' : '';
                const progressIndicator = isCompleted
                    ? `<div class="tool-call-completed-icon">✅</div>`
                    : `<div class="tool-call-progress"></div>`;

                return `
                    <div class="tool-call-item ${completedClass}" data-id="${toolCall.id}">
                        <div class="tool-call-icon" aria-hidden="true">${this.getToolIcon(toolCall.name)}</div>
                        <div class="tool-call-info">
                            <div class="tool-call-name">${toolCall.name}</div>
                            <div class="tool-call-description">${toolCall.description}</div>
                        </div>
                        ${progressIndicator}
                    </div>
                `;
            }).join('');
            
            content.innerHTML = `<div class="tool-call-active">${activeCallsHtml}</div>`;
        } else {
            content.innerHTML = `
                <div class="tool-call-idle">
                    <div class="idle-indicator">💤</div>
                    <div class="idle-text">No active tool calls</div>
                </div>
            `;
        }
    }
    
    /**
     * Get appropriate icon for tool name
     */
    getToolIcon(toolName) {
        const iconMap = {
            // Backend space API tools
            'get_iss_location': '🛰️',
            'get_spacex_launches': '🚀',
            'get_people_in_space': '👨‍🚀',
            'get_mars_weather': '🔴',
            'get_space_news': '📰',
            'get_near_earth_objects': '🌍',
            'get_apod': '📸',
            'get_space_weather': '☀️',
            
            // Code tools
            'codebase_search': '🔍',
            'grep': '📄',
            'read_file': '📖',
            'write': '✏️',
            'search_replace': '🔄',
            'run_terminal_cmd': '💻',
            'list_dir': '📁',
            'web_search': '🌐',
            'create_diagram': '📊',
            'fetch_pull_request': '🔗',
            'delete_file': '🗑️',
            'edit_notebook': '📓',
            'multi_edit': '✂️',
            'todo_write': '📝',
            'read_lints': '🔧',
            'glob_file_search': '🔎'
        };
        
        return iconMap[toolName] || '🛠️';
    }
    
    /**
     * Simulate tool call from chat interactions (for demo purposes)
     */
    simulateToolCallsFromMessage(message) {
        // This method can be enhanced to detect and simulate tool calls based on message content
        const lowerMessage = message.toLowerCase();
        
        if (lowerMessage.includes('search') || lowerMessage.includes('find')) {
            const toolCallId = this.startToolCall('codebase_search', 'Searching through codebase for relevant information');
            
            // Complete after random delay (1-3 seconds)
            setTimeout(() => {
                this.completeToolCall(toolCallId);
            }, Math.random() * 2000 + 1000);
        }
        
        if (lowerMessage.includes('file') || lowerMessage.includes('read')) {
            const toolCallId = this.startToolCall('read_file', 'Reading file contents');
            
            setTimeout(() => {
                this.completeToolCall(toolCallId);
            }, Math.random() * 1500 + 500);
        }
        
        if (lowerMessage.includes('web') || lowerMessage.includes('internet') || lowerMessage.includes('online')) {
            const toolCallId = this.startToolCall('web_search', 'Searching the web for information');
            
            setTimeout(() => {
                this.completeToolCall(toolCallId);
            }, Math.random() * 3000 + 1000);
        }
    }
    
    /**
     * Demo tool call functionality (for testing)
     */
    demoToolCall() {
        const tools = [
            { name: 'codebase_search', description: 'Searching for authentication methods' },
            { name: 'read_file', description: 'Reading configuration file' },
            { name: 'web_search', description: 'Looking up latest API documentation' },
            { name: 'grep', description: 'Finding function definitions' },
            { name: 'run_terminal_cmd', description: 'Running tests' }
        ];
        
        const randomTool = tools[Math.floor(Math.random() * tools.length)];
        const toolCallId = this.startToolCall(randomTool.name, randomTool.description);
        
        // Complete after 2-4 seconds
        setTimeout(() => {
            this.completeToolCall(toolCallId, 'Demo completed successfully');
        }, Math.random() * 2000 + 2000);
        
        this.showNotification(`Demo tool call started: ${randomTool.name}`, 'info');
    }

    /**
     * Send chat message
     */
    async sendMessage() {
        const chatInput = document.getElementById('chat-input');
        const message = chatInput.value.trim();
        
        if (!message) return;
        
        // Add user message to chat
        this.addMessageToChat(message, 'user');
        
        // Only simulate tool calls if WebSocket is not connected (fallback)
        if (!this.isConnected || this.ws.readyState !== WebSocket.OPEN) {
            this.simulateToolCallsFromMessage(message);
        }
        
        // Clear input and reset height
        chatInput.value = '';
        chatInput.style.height = 'auto';
        document.getElementById('char-counter').textContent = chatInput.maxLength;
        
        // Show typing indicator
        this.showTypingIndicator();
        
        try {
            // Send via WebSocket if connected, otherwise use HTTP
            if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'chat',
                    message: message,
                    chat_history: this.chatHistory.slice(-10) // Include chat history
                }));
            } else {
                // Fallback to HTTP API
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        message: message,
                        chat_history: this.chatHistory.slice(-10) // Last 10 messages
                    })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    this.hideTypingIndicator();
                    this.addMessageToChat(data.response, 'assistant');

                    // Render tool call events when using HTTP (serverless)
                    if (Array.isArray(data.tool_call_events)) {
                        data.tool_call_events.forEach((evt) => {
                            if (!evt || !evt.type) return;
                            if (evt.type === 'tool_call_start') {
                                this.startToolCall(evt.tool_name, evt.description || `Executing ${evt.tool_name}`, evt.tool_id);
                            } else if (evt.type === 'tool_call_complete') {
                                this.completeToolCall(evt.tool_id, evt.result || evt.error);
                            }
                        });
                    }
                } else {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.hideTypingIndicator();
            this.addMessageToChat('Sorry, I encountered an error processing your request. Please try again.', 'assistant');
        }
    }

    /**
     * Add message to chat with enhanced animations
     */
    addMessageToChat(message, sender) {
        const chatMessages = document.getElementById('chat-messages');
        this.hideTypingIndicator();

        const messageEl = document.createElement('div');
        messageEl.className = `message ${sender}-message`;
        
        // Add initial opacity for smooth animation
        messageEl.style.opacity = '0';
        messageEl.style.transform = sender === 'user' ? 'translateX(30px)' : 'translateX(-30px)';

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = sender === 'user' ? '🧑‍🚀' : '🚀';

        const contentWrapper = document.createElement('div');
        contentWrapper.className = 'message-content-wrapper';

        const content = document.createElement('div');
        content.className = 'message-content';
        content.innerHTML = marked.parse(message);

        const timestamp = document.createElement('div');
        timestamp.className = 'message-timestamp';
        timestamp.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        contentWrapper.appendChild(content);
        contentWrapper.appendChild(timestamp);
        messageEl.appendChild(avatar);
        messageEl.appendChild(contentWrapper);
        chatMessages.appendChild(messageEl);

        // Smooth scroll to bottom
        chatMessages.scrollTo({
            top: chatMessages.scrollHeight,
            behavior: 'smooth'
        });

        // Trigger animation
        requestAnimationFrame(() => {
            messageEl.style.opacity = '1';
            messageEl.style.transform = 'translateX(0)';
            messageEl.style.transition = 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
        });

        this.chatHistory.push({
            role: sender === 'user' ? 'user' : 'assistant',
            content: message,
            timestamp: new Date().toISOString()
        });

        if (this.chatHistory.length > 50) {
            this.chatHistory = this.chatHistory.slice(-40);
        }
    }

    /**
     * Clear chat messages
     */
    clearChat() {
        const chatMessages = document.getElementById('chat-messages');
        const welcomeMessage = chatMessages.querySelector('.welcome-message');
        
        // Remove all messages except the welcome message
        chatMessages.innerHTML = '';
        if (welcomeMessage) {
            chatMessages.appendChild(welcomeMessage);
        }
        
        // Reset chat history
        this.chatHistory = [];
        
        // Show notification
        this.showNotification('Chat cleared', 'info');
    }

    /**
     * Debug function to test chat history
     */
    async debugChatHistory() {
        try {
            const response = await fetch('/api/debug/chat-history', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: "Debug test message",
                    chat_history: this.chatHistory.slice(-10)
                })
            });
            
            if (response.ok) {
                const debug_data = await response.json();
                console.log('Chat History Debug Info:', debug_data);
                this.showNotification(`Chat history: ${debug_data.chat_history_length} messages`, 'info');
            } else {
                console.error('Debug request failed:', response.status);
            }
        } catch (error) {
            console.error('Error in debug chat history:', error);
        }
    }

    /**
     * Show typing indicator
     */
    showTypingIndicator() {
        const chatMessages = document.getElementById('chat-messages');
        if (document.getElementById('typing-indicator')) return;

        const typingEl = document.createElement('div');
        typingEl.className = 'message assistant-message typing-indicator';
        typingEl.id = 'typing-indicator';
        
        typingEl.innerHTML = `
            <div class="message-avatar">🚀</div>
            <div class="message-content">
                <div class="typing-dots">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        
        chatMessages.appendChild(typingEl);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    /**
     * Hide typing indicator
     */
    hideTypingIndicator() {
        const typingEl = document.getElementById('typing-indicator');
        if (typingEl) {
            typingEl.remove();
        }
    }

    /**
     * Append a chunk of a streamed message
     */
    appendMessageChunk(chunk) {
        this.hideTypingIndicator();
        let streamingMessageEl = document.getElementById('streaming-message');

        if (!streamingMessageEl) {
            streamingMessageEl = document.createElement('div');
            streamingMessageEl.id = 'streaming-message';
            streamingMessageEl.className = 'message assistant-message';
            
            streamingMessageEl.innerHTML = `
                <div class="message-avatar">🚀</div>
                <div class="message-content-wrapper">
                    <div class="message-content"></div>
                    <div class="message-timestamp"></div>
                </div>
            `;
            document.getElementById('chat-messages').appendChild(streamingMessageEl);
        }
        
        const contentEl = streamingMessageEl.querySelector('.message-content');
        contentEl.innerHTML += marked.parse(chunk);
        
        // Scroll to bottom
        const chatMessages = document.getElementById('chat-messages');
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    /**
     * Finalize a streamed message
     */
    finalizeMessage() {
        const streamingMessageEl = document.getElementById('streaming-message');
        if (streamingMessageEl) {
            const timestampEl = streamingMessageEl.querySelector('.message-timestamp');
            timestampEl.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            
            const content = streamingMessageEl.querySelector('.message-content').textContent;
            this.chatHistory.push({
                role: 'assistant',
                content: content,
                timestamp: new Date().toISOString()
            });

            streamingMessageEl.removeAttribute('id');
        }
    }

    /**
     * Initialize copy-to-clipboard for code blocks
     */
    initializeCopyButtons() {
        const chatMessages = document.getElementById('chat-messages');

        const addCopyButton = (preElement) => {
            const code = preElement.querySelector('code');
            if (!code) return;

            const button = document.createElement('button');
            button.className = 'copy-button';
            button.textContent = 'Copy';
            preElement.appendChild(button);

            button.addEventListener('click', () => {
                navigator.clipboard.writeText(code.innerText).then(() => {
                    button.textContent = 'Copied!';
                    setTimeout(() => {
                        button.textContent = 'Copy';
                    }, 2000);
                });
            });
        };

        // Observer to add copy buttons to new code blocks
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1) { // Element node
                        if (node.tagName === 'PRE') {
                            addCopyButton(node);
                        } else if (node.querySelectorAll) {
                            node.querySelectorAll('pre').forEach(addCopyButton);
                        }
                    }
                });
            });
        });

        observer.observe(chatMessages, { childList: true, subtree: true });

        // Initial run for existing elements
        chatMessages.querySelectorAll('pre').forEach(addCopyButton);
    }

    /**
     * Load initial data (ultra lightweight)
     */
    async loadInitialData() {
        // Load only the fastest APIs
        await Promise.all([
            this.loadISSData(),
            this.loadNextLaunch(),
            this.loadSpaceNews(),
            this.loadNEOData()
        ]);
        
        // Initialize static data
        this.initializeStaticWidgets();
        
        // Initialize tool call widget
        this.updateToolCallWidget();
    }

    /**
     * Load ISS data with cache awareness
     */
    async loadISSData() {
        try {
            const response = await fetch('/api/space-data/iss');
            const result = await response.json();
            
            if (result.data && !result.data.error) {
                const isCached = result.cached || result.data.cached;
                this.updateISSWidget(result.data, isCached);
                
                // Log cache status for debugging
                if (isCached) {
                    console.log('📦 ISS data served from cache');
                } else {
                    console.log('🔴 ISS data fetched live');
                }
            }
        } catch (error) {
            console.error('Error loading ISS data:', error);
            this.showError('iss-location', 'Unable to load ISS data');
        }
    }

    /**
     * Update ISS widget with cache indicators
     */
    updateISSWidget(issData, isCached = false) {
        const locationEl = document.getElementById('iss-location');
        const refreshEl = document.getElementById('iss-refresh');
        
        if (issData && issData.iss_position) {
            const { latitude, longitude } = issData.iss_position;
            const timestamp = new Date(issData.timestamp * 1000);
            const cacheIndicator = isCached ? '💾' : '🔴';
            const cacheText = isCached ? 'Cached' : 'Live';
            
            if (locationEl) {
                locationEl.innerHTML = `
                    <div><strong>📍 Current Position ${cacheIndicator}</strong></div>
                    <div>Lat: ${parseFloat(latitude).toFixed(2)}°</div>
                    <div>Lon: ${parseFloat(longitude).toFixed(2)}°</div>
                    <div style="font-size: 0.8rem; color: var(--space-gray); margin-top: 0.5rem;" data-updated="${timestamp.toISOString()}">
                        Updated: ${this.toRelativeTime(timestamp)}
                    </div>
                    <div style="font-size: 0.7rem; color: ${isCached ? 'var(--space-gold)' : 'var(--space-green)'}; margin-top: 0.3rem;">
                        ${cacheText} Data
                    </div>
                `;
            }
            
            // Update refresh indicator based on cache status
            if (refreshEl) {
                const color = isCached ? 'var(--space-gold)' : 'var(--space-green)';
                refreshEl.style.background = color;
                refreshEl.title = isCached ? 'Data from cache' : 'Live data';
            }
        }
    }

    /**
     * Load people in space data with cache awareness
     */
    async loadPeopleInSpace() {
        try {
            const response = await fetch('/api/space-data/people-in-space');
            const result = await response.json();
            
            if (result.data && !result.data.error) {
                const isCached = result.cached || result.data.cached;
                this.updatePeopleInSpaceWidget(result.data, isCached);
            }
        } catch (error) {
            console.error('Error loading people in space data:', error);
            this.showError('people-content', 'Unable to load data');
        }
    }

    /**
     * Update people in space widget
     */
    updatePeopleInSpaceWidget(peopleData, isCached = false) {
        const countEl = document.getElementById('people-count');
        const namesEl = document.getElementById('people-names');
        const refreshEl = document.getElementById('people-refresh');
        
        if (countEl && namesEl && peopleData && peopleData.people) {
            countEl.textContent = peopleData.number || '--';
            
            const names = peopleData.people.map(p => p.name.split(' ')[0]).join(', ');
            namesEl.textContent = names;
            
            if (refreshEl) {
                const color = isCached ? 'var(--space-gold)' : 'var(--space-green)';
                refreshEl.style.background = color;
                refreshEl.title = isCached ? 'Data from cache' : 'Live data';
            }
        }
    }

    /**
     * Load planetary data with rotation
     */
    async loadPlanetaryData() {
        const planets = ['sun', 'moon', 'mars', 'jupiter', 'saturn', 'earth'];
        if (!this.currentPlanetIndex || this.currentPlanetIndex >= planets.length) {
            this.currentPlanetIndex = 0;
        }
        
        const planetId = planets[this.currentPlanetIndex];
        
        try {
            const response = await fetch(`/api/space-data/planet-${planetId}`);
            const result = await response.json();
            
            if (result.data && !result.data.error) {
                const isCached = result.cached || result.data.cached;
                this.updatePlanetaryWidget(result.data, isCached);
            }
        } catch (error) {
            console.error(`Error loading data for ${planetId}:`, error);
            this.showError('planet-stats', 'Unable to load data');
        }

        this.currentPlanetIndex++;
    }

    /**
     * Update planetary widget
     */
    updatePlanetaryWidget(planetData, isCached = false) {
        const nameEl = document.getElementById('planet-name');
        const statsEl = document.getElementById('planet-stats');
        const refreshEl = document.getElementById('planet-refresh');

        if (nameEl && statsEl && planetData) {
            nameEl.textContent = `🪐 ${planetData.englishName || 'Solar Body'}`;
            
            const stats = [
                { label: 'Gravity', value: planetData.gravity, unit: 'm/s²' },
                { label: 'Radius', value: planetData.meanRadius, unit: 'km' },
                { label: 'Moons', value: planetData.moons ? planetData.moons.length : 0, unit: '' }
            ];

            statsEl.innerHTML = stats.map(s => `
                <div class="stat-item">
                    <div class="stat-value">${s.value || '--'} ${s.unit}</div>
                    <div class="stat-label">${s.label}</div>
                </div>
            `).join('');

            if (refreshEl) {
                const color = isCached ? 'var(--space-gold)' : 'var(--space-green)';
                refreshEl.style.background = color;
                refreshEl.title = isCached ? 'Data from cache' : 'Live data';
            }
        }
    }

    /**
     * Load next launch with cache awareness
     */
    async loadNextLaunch() {
        try {
            const response = await fetch('/api/space-data/spacex-next');
            const result = await response.json();
            
            if (result.data && !result.data.error) {
                const isCached = result.cached || result.data.cached;
                this.updateNextLaunchWidget(result.data, isCached);
                
                // Log cache status for debugging
                if (isCached) {
                    console.log('📦 Launch data served from cache');
                } else {
                    console.log('🚀 Launch data fetched live');
                }
            }
        } catch (error) {
            console.error('Error loading next launch:', error);
            this.showError('launches-content', 'Unable to load launch data');
        }
    }

    /**
     * Update next launch widget with cache indicators
     */
    updateNextLaunchWidget(launchData, isCached = false) {
        const contentEl = document.getElementById('launches-content');
        const refreshEl = document.getElementById('launch-refresh');
        
        if (contentEl && launchData) {
            const date = new Date(launchData.date_utc);
            const timeUntil = this.getTimeUntilLaunch(date);
            const cacheIndicator = isCached ? '💾' : '🚀';
            const cacheText = isCached ? 'Cached' : 'Live';
            
            contentEl.innerHTML = `
                <div class="launch-item">
                    <div class="launch-title">${launchData.name || 'TBD Mission'}</div>
                    <div class="launch-date" data-launch-date="${date.toISOString()}">${date.toLocaleDateString()}</div>
                    <div class="launch-countdown" data-launch-countdown="${date.toISOString()}">${timeUntil}</div>
                    <div class="launch-status status-upcoming">Upcoming ${cacheIndicator}</div>
                    <div style="font-size: 0.7rem; color: ${isCached ? 'var(--space-gold)' : 'var(--space-green)'}; margin-top: 0.5rem;">
                        ${cacheText} Data
                    </div>
                </div>
            `;
            
            // Update refresh indicator based on cache status
            if (refreshEl) {
                const color = isCached ? 'var(--space-gold)' : 'var(--space-green)';
                refreshEl.style.background = color;
                refreshEl.title = isCached ? 'Data from cache' : 'Live data';
            }
        }
    }

    /**
     * Load Space News data
     */
    async loadSpaceNews() {
        try {
            const response = await fetch('/api/space-data/space-news');
            const result = await response.json();
            
            if (result.data && !result.data.error) {
                const isCached = result.cached || result.data.cached;
                this.updateSpaceNewsWidget(result.data, isCached);
            }
        } catch (error) {
            console.error('Error loading Space News:', error);
            this.showError('space-news-content', 'Unable to load data');
        }
    }

    /**
     * Update Space News widget
     */
    updateSpaceNewsWidget(newsData, isCached = false) {
        const contentEl = document.getElementById('space-news-content');
        const refreshEl = document.getElementById('space-news-refresh');
        
        if (contentEl && newsData.articles) {
            // Limit to only 4 news items
            const limitedArticles = newsData.articles.slice(0, 4);
            contentEl.innerHTML = limitedArticles.map(article => `
                <div class="news-item">
                    <a href="${article.url}" target="_blank">${article.title}</a>
                </div>
            `).join('');
            
            if (refreshEl) {
                const color = isCached ? 'var(--space-gold)' : 'var(--space-green)';
                refreshEl.style.background = color;
                refreshEl.title = isCached ? 'Data from cache' : 'Live data';
            }
        }
    }

    /**
     * Load Near-Earth Object data
     */
    async loadNEOData() {
        try {
            const response = await fetch('/api/space-data/near-earth-objects');
            const result = await response.json();
            
            if (result.data && !result.data.error) {
                const isCached = result.cached || result.data.cached;
                this.updateNEOWidget(result.data, isCached);
            }
        } catch (error) {
            console.error('Error loading NEO data:', error);
            this.showError('neo-content', 'Unable to load data');
        }
    }

    /**
     * Update NEO widget
     */
    updateNEOWidget(neoData, isCached = false) {
        const contentEl = document.getElementById('neo-content');
        const refreshEl = document.getElementById('neo-refresh');

        if (contentEl && neoData.near_earth_objects) {
            const today = new Date().toISOString().split('T')[0];
            const objectsToday = neoData.near_earth_objects[today] || [];
            
            contentEl.innerHTML = `
                <div class="stat-item">
                    <div class="stat-value">${neoData.element_count}</div>
                    <div class="stat-label">Total Objects</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${objectsToday.length}</div>
                    <div class="stat-label">Passing Today</div>
                </div>
            `;

            if (refreshEl) {
                const color = isCached ? 'var(--space-gold)' : 'var(--space-green)';
                refreshEl.style.background = color;
                refreshEl.title = isCached ? 'Data from cache' : 'Live data';
            }
        }
    }

    /**
     * Load space weather data with cache awareness
     */
    async loadSpaceWeather() {
        try {
            const response = await fetch('/api/space-data/space-weather');
            const result = await response.json();
            
            if (result.data && !result.data.error) {
                const isCached = result.cached || result.data.cached;
                this.updateSpaceWeatherWidget(result.data, isCached);
            }
        } catch (error) {
            console.error('Error loading space weather:', error);
            this.showError('weather-content', 'Unable to load data');
        }
    }

    /**
     * Update space weather widget
     */
    updateSpaceWeatherWidget(weatherData, isCached = false) {
        const contentEl = document.getElementById('weather-content');
        const refreshEl = document.getElementById('weather-refresh');

        if (contentEl && weatherData && weatherData.space_weather_news) {
            contentEl.innerHTML = weatherData.space_weather_news.map(n => `
                <div class="news-item">
                    <a href="${n.url}" target="_blank">${n.title}</a>
                </div>
            `).join('');

            if (refreshEl) {
                const color = isCached ? 'var(--space-gold)' : 'var(--space-green)';
                refreshEl.style.background = color;
                refreshEl.title = isCached ? 'Data from cache' : 'Live data';
            }
        }
    }

    /**
     * Get time until launch
     */
    getTimeUntilLaunch(launchDate) {
        const now = new Date();
        const diff = launchDate - now;
        
        if (diff <= 0) return 'Launch time passed';
        
        const days = Math.floor(diff / (1000 * 60 * 60 * 24));
        const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);
        if (days > 0) return `T-${days}d ${hours}h`;
        if (hours > 0) return `T-${hours}h ${minutes}m`;
        return `T-${minutes}m ${seconds}s`;
    }

    toRelativeTime(date) {
        const diff = (Date.now() - new Date(date).getTime()) / 1000;
        if (diff < 60) return `${Math.floor(diff)}s ago`;
        if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
        return `${Math.floor(diff/86400)}d ago`;
    }

    /**
     * Initialize static widgets (no API calls)
     */
    initializeStaticWidgets() {
        // Space facts are now dynamic
        // Initialize time display
        this.updateTimeDisplay();
        
        // Calculate ISS orbits today (approximate)
        const now = new Date();
        const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const minutesSinceStartOfDay = (now - startOfDay) / (1000 * 60);
        const orbitsToday = Math.floor(minutesSinceStartOfDay / 90); // ISS orbit is ~90 minutes
        
        this.updateStat('iss-orbits', orbitsToday);
    }

    /**
     * Update time display
     */
    updateTimeDisplay() {
        const now = new Date();
        const utcTime = now.toUTCString().split(' ')[4]; // Get just the time part
        this.updateStat('current-time', utcTime);

        // Update any relative timestamps
        document.querySelectorAll('[data-updated]').forEach(el => {
            const iso = el.getAttribute('data-updated');
            if (iso) {
                el.textContent = `Updated: ${this.toRelativeTime(iso)}`;
            }
        });

        // Update any launch countdowns
        document.querySelectorAll('[data-launch-countdown]').forEach(el => {
            const iso = el.getAttribute('data-launch-countdown');
            if (iso) {
                const launchDate = new Date(iso);
                el.textContent = this.getTimeUntilLaunch(launchDate);
            }
        });
    }

    /**
     * Update a stat value
     */
    updateStat(statId, value) {
        const element = document.getElementById(statId);
        if (element) {
            element.textContent = value;
            element.classList.add('cosmic-glow');
            setTimeout(() => {
                element.classList.remove('cosmic-glow');
            }, 2000);
        }
    }

    /**
     * Show error in widget with better styling
     */
    showError(elementId, message) {
        const element = document.getElementById(elementId);
        if (element) {
            element.innerHTML = `
                <div style="
                    color: var(--space-pink); 
                    text-align: center; 
                    padding: 1.5rem;
                    background: rgba(255, 0, 110, 0.1);
                    border: 1px solid rgba(255, 0, 110, 0.3);
                    border-radius: 8px;
                    font-size: 0.9rem;
                    animation: fadeIn 0.3s ease;
                ">
                    <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">⚠️</div>
                    ${message}
                </div>
            `;
        }
    }

    /**
     * Show loading overlay with enhanced animation
     */
    showLoadingOverlay() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.display = 'flex';
            overlay.style.opacity = '0';
            requestAnimationFrame(() => {
                overlay.style.opacity = '1';
                overlay.style.transition = 'opacity 0.3s ease';
            });
        }
    }

    /**
     * Hide loading overlay
     */
    hideLoadingOverlay() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.opacity = '0';
            setTimeout(() => {
                overlay.style.display = 'none';
            }, 500);
        }
    }

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 1rem 1.5rem;
            background: rgba(26, 26, 46, 0.9);
            border: 1px solid var(--space-cyan);
            border-radius: 8px;
            color: var(--space-white);
            z-index: 10000;
            animation: slideIn 0.3s ease;
        `;
        
        if (type === 'error') {
            notification.style.borderColor = 'var(--space-pink)';
            notification.style.background = 'rgba(255, 0, 110, 0.1)';
        }
        
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 5000);
    }

    /**
     * Cleanup on page unload
     */
    destroy() {
        // Clear intervals
        Object.values(this.updateIntervals).forEach(interval => {
            clearInterval(interval);
        });
        
        // Close WebSocket
        if (this.ws) {
            this.ws.close();
        }
    }
}

// CSS for notifications
const notificationCSS = `
@keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}

@keyframes slideOut {
    from { transform: translateX(0); opacity: 1; }
    to { transform: translateX(100%); opacity: 0; }
}
`;

const style = document.createElement('style');
style.textContent = notificationCSS;
document.head.appendChild(style);

// Initialize application when DOM is loaded
let app;

document.addEventListener('DOMContentLoaded', () => {
    app = new AntrikshGPT();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (app) {
        app.destroy();
    }
});

// Global error handler
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    if (app) {
        app.showNotification('An unexpected error occurred', 'error');
    }
});