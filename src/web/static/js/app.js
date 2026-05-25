// Main application logic
const appState = {
    streaming: false,
    frameRequested: false,
    metrics: {
        frameCount: 0,
        fpsStartTime: null,
        fpsFrameCount: 0,
        latencyHistory: [],
        t1History: [],
        t2History: [],
        t3History: [],
        t4History: [],
        t5History: []
    }
};

// DOM elements
const elements = {
    canvas: document.getElementById('videoCanvas'),
    ctx: document.getElementById('videoCanvas').getContext('2d'),
    status: document.getElementById('status'),
    startBtn: document.getElementById('startBtn'),
    stopBtn: document.getElementById('stopBtn'),
    connectBtn: document.getElementById('connectBtn'),
    refreshBtn: document.getElementById('refreshBtn'),
    exportBtn: document.getElementById('exportBtn'),
    frameCount: document.getElementById('frameCount'),
    totalLatency: document.getElementById('totalLatency'),
    fpsCounter: document.getElementById('fpsCounter'),
    resolution: document.getElementById('resolution'),
    httpsUrl: document.getElementById('httpsUrl'),
    wsUrl: document.getElementById('wsUrl'),
    t1Capture: document.getElementById('t1Capture'),
    t2Processing: document.getElementById('t2Processing'),
    t3Network: document.getElementById('t3Network'),
    t4Decoding: document.getElementById('t4Decoding'),
    t5Rendering: document.getElementById('t5Rendering'),
    latencyTotal: document.getElementById('latencyTotal')
};

// Initialize URLs
function initializeUrls() {
    const serverIp = window.location.hostname || 'localhost';
    elements.httpsUrl.textContent = `https://${serverIp}:8000`;
    elements.wsUrl.textContent = `wss://${serverIp}:3001`;
}

// Update status display
function updateStatus(message, isError = false) {
    elements.status.textContent = "Status: " + message;
    if (isError) {
        elements.status.style.borderLeftColor = '#f44336';
        elements.status.style.background = '#ffebee';
    } else {
        elements.status.style.borderLeftColor = '#4CAF50';
        elements.status.style.background = '#f8f9fa';
    }
    console.log("Status:", message);
}

// Update FPS counter
function updateFPS() {
    const now = performance.now();
    if (!appState.metrics.fpsStartTime) {
        appState.metrics.fpsStartTime = now;
        appState.metrics.fpsFrameCount = 0;
    }
    
    appState.metrics.fpsFrameCount++;
    
    if (now - appState.metrics.fpsStartTime >= 1000) {
        const fps = (appState.metrics.fpsFrameCount * 1000) / (now - appState.metrics.fpsStartTime);
        elements.fpsCounter.textContent = fps.toFixed(1);
        appState.metrics.fpsStartTime = now;
        appState.metrics.fpsFrameCount = 0;
    }
}

// WebSocket message handler
async function onWebSocketMessage(event) {
    appState.frameRequested = false;
    
    try {
        const data = JSON.parse(event.data);
        
        if (data.metadata && data.image_data) {
            // Start T4 decoding measurement
            const decodeStartTime = performance.now();
            
            // Convert hex string back to bytes
            const hexString = data.image_data;
            const byteArray = new Uint8Array(hexString.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
            
            // Create blob and decode image
            const blob = new Blob([byteArray], { type: 'image/jpeg' });
            const imageBitmap = await createImageBitmap(blob);
            
            // End T4 decoding measurement
            const decodeEndTime = performance.now();
            const t4Decoding = decodeEndTime - decodeStartTime;
            
            // Start T5 rendering measurement
            const renderStartTime = performance.now();
            
            // Draw to canvas
            elements.ctx.clearRect(0, 0, elements.canvas.width, elements.canvas.height);
            elements.ctx.drawImage(imageBitmap, 0, 0, elements.canvas.width, elements.canvas.height);
            
            // End T5 rendering measurement
            const renderEndTime = performance.now();
            const t5Rendering = renderEndTime - renderStartTime;
            
            // Calculate T3 network latency using RTT/2
            let t3Network = 5; // Default value

            if (window.lastFrameRequestTime) {
                const roundTripTime = performance.now() - window.lastFrameRequestTime;
                t3Network = Math.max(0, roundTripTime / 2);
                t3Network = Math.min(Math.max(t3Network, 1), 200);
            }

            // Store request time for next frame
            window.lastFrameRequestTime = performance.now();
            
            // Calculate total latency
            const totalLatency = t3Network + t4Decoding + t5Rendering;
            
            // Update display
            elements.frameCount.textContent = ++appState.metrics.frameCount;
            elements.totalLatency.textContent = totalLatency.toFixed(1);
            elements.resolution.textContent = `${imageBitmap.width}x${imageBitmap.height}`;
            
            // Update latency breakdown
            elements.t1Capture.textContent = data.metadata.t1_capture.toFixed(1);
            elements.t2Processing.textContent = data.metadata.t2_processing.toFixed(1);
            elements.t3Network.textContent = t3Network.toFixed(1);
            elements.t4Decoding.textContent = t4Decoding.toFixed(1);
            elements.t5Rendering.textContent = t5Rendering.toFixed(1);
            elements.latencyTotal.textContent = totalLatency.toFixed(1);
            
            // Update FPS
            updateFPS();
            
            // Send latency report back to server
            const latencyReport = {
                type: "latency_report",
                data: {
                    t1_capture: data.metadata.t1_capture,
                    t2_processing: data.metadata.t2_processing,
                    t3_network: t3Network,
                    t4_decoding: t4Decoding,
                    t5_rendering: t5Rendering,
                    total: totalLatency,
                    frame_index: data.metadata.frame_index
                }
            };
            
            WebSocketManager.send(latencyReport);
            
            updateStatus(`Streaming - Frame: ${appState.metrics.frameCount} | Latency: ${totalLatency.toFixed(1)}ms`);
            
            // Store history
            appState.metrics.latencyHistory.push(totalLatency);
            appState.metrics.t1History.push(data.metadata.t1_capture);
            appState.metrics.t2History.push(data.metadata.t2_processing);
            appState.metrics.t3History.push(t3Network);
            appState.metrics.t4History.push(t4Decoding);
            appState.metrics.t5History.push(t5Rendering);
            
            // Keep only last 100 samples
            if (appState.metrics.latencyHistory.length > 100) {
                appState.metrics.latencyHistory.shift();
                appState.metrics.t1History.shift();
                appState.metrics.t2History.shift();
                appState.metrics.t3History.shift();
                appState.metrics.t4History.shift();
                appState.metrics.t5History.shift();
            }
            
            // Request next frame if still streaming
            if (appState.streaming) {
                setTimeout(requestFrame, 16); // ~60 FPS
            }
        }
    } catch (error) {
        console.error("Error processing frame:", error);
        updateStatus("Error processing frame", true);
    }
}

// Request a frame from server
function requestFrame() {
    if (!appState.streaming || appState.frameRequested || !WebSocketManager.isConnected()) {
        return;
    }
    
    appState.frameRequested = true;
    
    // Store timestamp for RTT calculation
    window.lastFrameRequestTime = performance.now();
    
    try {
        const requestData = {
            type: "request_frame",
            t1_capture: appState.metrics.t1History.length > 0 ? 
                    appState.metrics.t1History[appState.metrics.t1History.length - 1] : 0
        };
        WebSocketManager.send(requestData);
        appState.frameRequested = false;
    } catch (error) {
        console.error("Error sending frame request:", error);
        updateStatus("Error requesting frame", true);
        appState.frameRequested = false;
    }
}

// Start streaming
function startStream() {
    console.log("startStream called");
    if (!appState.streaming && WebSocketManager.isConnected()) {
        appState.streaming = true;
        elements.startBtn.disabled = true;
        elements.stopBtn.disabled = false;
        updateStatus("Starting stream...");
        appState.metrics.frameCount = 0;
        elements.frameCount.textContent = "0";
        requestFrame();
    } else if (!WebSocketManager.isConnected()) {
        updateStatus("WebSocket not connected. Click 'Connect' first.", true);
    }
}

// Stop streaming
function stopStream() {
    console.log("stopStream called");
    appState.streaming = false;
    elements.startBtn.disabled = false;
    elements.stopBtn.disabled = true;
    updateStatus("Stream stopped");
    elements.ctx.clearRect(0, 0, elements.canvas.width, elements.canvas.height);
}

// Connect WebSocket
function connectWebSocket() {
    updateStatus("Connecting to WebSocket...");
    elements.connectBtn.disabled = true;
    
    WebSocketManager.connect(
        // onOpen
        () => {
            updateStatus("Connected! Click 'Start Stream' to begin.");
            WebSocketManager.reconnectAttempts = 0;
            elements.startBtn.disabled = false;
            console.log("WebSocket connection established");
        },
        // onMessage
        onWebSocketMessage,
        // onClose
        (event) => {
            updateStatus(`Disconnected. Code: ${event.code}, Reason: ${event.reason || 'Unknown'}`, true);
            elements.connectBtn.disabled = false;
            elements.startBtn.disabled = true;
            elements.stopBtn.disabled = true;
            
            if (appState.streaming && WebSocketManager.reconnectAttempts < WebSocketManager.maxReconnectAttempts) {
                WebSocketManager.reconnectAttempts++;
                updateStatus(`Reconnecting (attempt ${WebSocketManager.reconnectAttempts}/${WebSocketManager.maxReconnectAttempts})...`);
                setTimeout(connectWebSocket, 2000);
            }
        },
        // onError
        (error) => {
            updateStatus("Connection error", true);
            console.error("WebSocket error:", error);
            elements.connectBtn.disabled = false;
        }
    );
}

// Export metrics to CSV
function exportMetrics() {
    if (appState.metrics.latencyHistory.length === 0) {
        updateStatus("No metrics to export", true);
        return;
    }
    
    const csvContent = [
        ['Frame', 'T1 Capture', 'T2 Processing', 'T3 Network', 'T4 Decoding', 'T5 Rendering', 'Total'],
        ...appState.metrics.latencyHistory.map((total, index) => [
            index + 1,
            appState.metrics.t1History[index] || 0,
            appState.metrics.t2History[index] || 0,
            appState.metrics.t3History[index] || 0,
            appState.metrics.t4History[index] || 0,
            appState.metrics.t5History[index] || 0,
            total
        ])
    ].map(row => row.join(',')).join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `latency_metrics_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    updateStatus("Metrics exported to CSV file");
}

// Initialize event listeners
function initializeEventListeners() {
    elements.startBtn.addEventListener('click', startStream);
    elements.stopBtn.addEventListener('click', stopStream);
    elements.connectBtn.addEventListener('click', connectWebSocket);
    elements.refreshBtn.addEventListener('click', () => location.reload());
    elements.exportBtn.addEventListener('click', exportMetrics);
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.key === ' ' || e.key === 'Spacebar') {
            e.preventDefault();
            if (appState.streaming) {
                stopStream();
            } else {
                startStream();
            }
        } else if (e.key === 'c' || e.key === 'C') {
            e.preventDefault();
            connectWebSocket();
        } else if (e.key === 'r' || e.key === 'R') {
            e.preventDefault();
            location.reload();
        } else if (e.key === 'e' || e.key === 'E') {
            e.preventDefault();
            exportMetrics();
        }
    });
    
    // Clean up on page unload
    window.addEventListener('beforeunload', function() {
        appState.streaming = false;
        WebSocketManager.disconnect();
    });
}

// Initialize application
function initializeApp() {
    console.log("Initializing application...");
    initializeUrls();
    initializeEventListeners();
    updateStatus("Page loaded. Click .u.jhgmjjjh'Connect' to begin.");
    
    // Auto-connect after 1 second
    setTimeout(() => {
        console.log("Auto-connecting WebSocket...");
        connectWebSocket();
    }, 1000);
}

// Start the application when page loads
window.addEventListener('load', initializeApp);