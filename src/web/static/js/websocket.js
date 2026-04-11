// WebSocket connection handling module
const WebSocketManager = {
    connection: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 10,
    
    connect(onOpenCallback, onMessageCallback, onCloseCallback, onErrorCallback) {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsHost = window.location.hostname;
        const wsUrl = `${wsProtocol}//${wsHost}:3001`;
        
        console.log("Connecting to WebSocket:", wsUrl);
        
        this.connection = new WebSocket(wsUrl);
        
        this.connection.onopen = function() {
            console.log("WebSocket connection opened");
            if (onOpenCallback) onOpenCallback();
        };
        
        this.connection.onmessage = async function(event) {
            if (onMessageCallback) await onMessageCallback(event);
        };
        
        this.connection.onclose = function(event) {
            console.log("WebSocket connection closed:", event);
            if (onCloseCallback) onCloseCallback(event);
        };
        
        this.connection.onerror = function(error) {
            console.error("WebSocket error:", error);
            if (onErrorCallback) onErrorCallback(error);
        };
        
        return this.connection;
    },
    
    disconnect() {
        if (this.connection && this.connection.readyState === WebSocket.OPEN) {
            this.connection.close();
        }
        this.connection = null;
    },
    
    send(message) {
        if (this.connection && this.connection.readyState === WebSocket.OPEN) {
            this.connection.send(JSON.stringify(message));
            return true;
        }
        return false;
    },
    
    isConnected() {
        return this.connection && this.connection.readyState === WebSocket.OPEN;
    },
    
    getState() {
        return this.connection ? this.connection.readyState : -1;
    }
};