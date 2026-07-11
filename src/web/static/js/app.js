/**
 * Aplicação cliente para streaming de vídeo com medição de latência
 * 
 * Este script gerencia a conexão WebSocket, receção de frames,
 * medição de latência (T1 a T5), exibição no canvas e exportação de métricas.
 */

// ============================================================
// ESTADO DA APLICAÇÃO
// ============================================================
const appState = {
    streaming: false,          // Indica se o stream está ativo
    frameRequested: false,     // Previne pedidos duplicados de frames
    metrics: {
        frameCount: 0,         // Contador de frames recebidos
        fpsStartTime: null,    // Tempo de início para cálculo de FPS
        fpsFrameCount: 0,      // Contador de frames para FPS
        latencyHistory: [],    // Histórico de latência total
        t1History: [],         // Histórico de T1 (captura)
        t2History: [],         // Histórico de T2 (processamento servidor)
        t3History: [],         // Histórico de T3 (rede)
        t4History: [],         // Histórico de T4 (descodificação)
        t5History: []          // Histórico de T5 (rendering)
    }
};

// ============================================================
// REFERÊNCIAS AOS ELEMENTOS DOM
// ============================================================
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

// ============================================================
// FUNÇÕES DE INICIALIZAÇÃO
// ============================================================

/**
 * Inicializa as URLs do servidor HTTPS e WebSocket
 */
function initializeUrls() {
    const serverIp = window.location.hostname || 'localhost';
    elements.httpsUrl.textContent = `https://${serverIp}:8000`;
    elements.wsUrl.textContent = `wss://${serverIp}:3001`;
}

// ============================================================
// FUNÇÕES DE INTERFACE
// ============================================================

/**
 * Atualiza a mensagem de estado na interface
 * 
 * @param {string} message - Mensagem a exibir
 * @param {boolean} isError - Se true, exibe com estilo de erro
 */
function updateStatus(message, isError = false) {
    elements.status.textContent = "Status: " + message;
    if (isError) {
        elements.status.style.borderLeftColor = '#f44336';  // Vermelho (erro)
        elements.status.style.background = '#ffebee';
    } else {
        elements.status.style.borderLeftColor = '#4CAF50';  // Verde (ok)
        elements.status.style.background = '#f8f9fa';
    }
    console.log("Estado:", message);
}

/**
 * Atualiza o contador de FPS na interface
 */
function updateFPS() {
    const now = performance.now();
    if (!appState.metrics.fpsStartTime) {
        appState.metrics.fpsStartTime = now;
        appState.metrics.fpsFrameCount = 0;
    }
    
    appState.metrics.fpsFrameCount++;
    
    // Calcula o FPS a cada segundo
    if (now - appState.metrics.fpsStartTime >= 1000) {
        const fps = (appState.metrics.fpsFrameCount * 1000) / (now - appState.metrics.fpsStartTime);
        elements.fpsCounter.textContent = fps.toFixed(1);
        appState.metrics.fpsStartTime = now;
        appState.metrics.fpsFrameCount = 0;
    }
}

// ============================================================
// FUNÇÕES DE PROCESSAMENTO WEBSOCKET
// ============================================================

/**
 * Handler para mensagens recebidas via WebSocket
 * Processa o frame e mede a latência (T4 e T5)
 * 
 * @param {MessageEvent} event - Evento da mensagem WebSocket
 */
async function onWebSocketMessage(event) {
    appState.frameRequested = false;
    
    try {
        const data = JSON.parse(event.data);
        
        // Verifica se contém dados de imagem
        if (data.metadata && data.image_data) {
            // ============================================================
            // T4: MEDIÇÃO DO TEMPO DE DESCODIFICAÇÃO
            // ============================================================
            const decodeStartTime = performance.now();
            
            // Converte string hexadecimal para bytes
            const hexString = data.image_data;
            const byteArray = new Uint8Array(hexString.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
            
            // Cria um Blob e descodifica a imagem
            const blob = new Blob([byteArray], { type: 'image/jpeg' });
            const imageBitmap = await createImageBitmap(blob);
            
            // Fim da medição T4
            const decodeEndTime = performance.now();
            const t4Decoding = decodeEndTime - decodeStartTime;
            
            // ============================================================
            // T5: MEDIÇÃO DO TEMPO DE RENDERIZAÇÃO
            // ============================================================
            const renderStartTime = performance.now();
            
            // Desenha a imagem no canvas
            elements.ctx.clearRect(0, 0, elements.canvas.width, elements.canvas.height);
            elements.ctx.drawImage(imageBitmap, 0, 0, elements.canvas.width, elements.canvas.height);
            
            // Fim da medição T5
            const renderEndTime = performance.now();
            const t5Rendering = renderEndTime - renderStartTime;
            
            // ============================================================
            // T3: CÁLCULO DA LATÊNCIA DE REDE (RTT/2)
            // ============================================================
            let t3Network = 5; // Valor padrão

            if (window.lastFrameRequestTime) {
                const roundTripTime = performance.now() - window.lastFrameRequestTime;
                t3Network = Math.max(0, roundTripTime / 2);  // Estima o sentido único
                t3Network = Math.min(Math.max(t3Network, 1), 200);  // Limita entre 1 e 200ms
            }

            // Armazena o tempo do pedido para o próximo frame
            window.lastFrameRequestTime = performance.now();
            
            // ============================================================
            // CÁLCULO DA LATÊNCIA TOTAL
            // ============================================================
            const totalLatency = t3Network + t4Decoding + t5Rendering;
            
            // ============================================================
            // ATUALIZAÇÃO DA INTERFACE
            // ============================================================
            elements.frameCount.textContent = ++appState.metrics.frameCount;
            elements.totalLatency.textContent = totalLatency.toFixed(1);
            elements.resolution.textContent = `${imageBitmap.width}x${imageBitmap.height}`;
            
            // Atualiza a decomposição da latência
            elements.t1Capture.textContent = data.metadata.t1_capture.toFixed(1);
            elements.t2Processing.textContent = data.metadata.t2_processing.toFixed(1);
            elements.t3Network.textContent = t3Network.toFixed(1);
            elements.t4Decoding.textContent = t4Decoding.toFixed(1);
            elements.t5Rendering.textContent = t5Rendering.toFixed(1);
            elements.latencyTotal.textContent = totalLatency.toFixed(1);
            
            // Atualiza o FPS
            updateFPS();
            
            // ============================================================
            // ENVIO DO RELATÓRIO DE LATÊNCIA PARA O SERVIDOR
            // ============================================================
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
            
            // ============================================================
            // ATUALIZAÇÃO DO ESTADO
            // ============================================================
            updateStatus(`Streaming - Frame: ${appState.metrics.frameCount} | Latency: ${totalLatency.toFixed(1)}ms`);
            
            // ============================================================
            // ARMAZENAMENTO DO HISTÓRICO (MANTÉM APENAS OS ÚLTIMOS 100)
            // ============================================================
            appState.metrics.latencyHistory.push(totalLatency);
            appState.metrics.t1History.push(data.metadata.t1_capture);
            appState.metrics.t2History.push(data.metadata.t2_processing);
            appState.metrics.t3History.push(t3Network);
            appState.metrics.t4History.push(t4Decoding);
            appState.metrics.t5History.push(t5Rendering);
            
            // Remove o mais antigo se exceder 100 amostras
            if (appState.metrics.latencyHistory.length > 100) {
                appState.metrics.latencyHistory.shift();
                appState.metrics.t1History.shift();
                appState.metrics.t2History.shift();
                appState.metrics.t3History.shift();
                appState.metrics.t4History.shift();
                appState.metrics.t5History.shift();
            }
            
            // ============================================================
            // SOLICITA O PRÓXIMO FRAME (A ~60 FPS)
            // ============================================================
            if (appState.streaming) {
                setTimeout(requestFrame, 16); // ~60 FPS
            }
        }
    } catch (error) {
        console.error("Quadro de processamento de erros:", error);
        updateStatus("Quadro de processamento de erros", true);
    }
}

// ============================================================
// FUNÇÕES DE CONTROLO
// ============================================================

/**
 * Solicita um frame ao servidor
 */
function requestFrame() {
    // Verifica se está em streaming e se a conexão está ativa
    if (!appState.streaming || appState.frameRequested || !WebSocketManager.isConnected()) {
        return;
    }
    
    appState.frameRequested = true;
    
    // Armazena o timestamp para cálculo do RTT
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
        console.error("Erro ao enviar pedido de quadro:", error);
        updateStatus("Erro ao solicitar o quadro", true);
        appState.frameRequested = false;
    }
}

/**
 * Inicia o streaming
 */
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
        updateStatus("WebSocket não ligado. Clique em 'Ligar' primeiro.", true);
    }
}

/**
 * Para o streaming
 */
function stopStream() {
    console.log("stopStream called");
    appState.streaming = false;
    elements.startBtn.disabled = false;
    elements.stopBtn.disabled = true;
    updateStatus("Stream stopped");
    elements.ctx.clearRect(0, 0, elements.canvas.width, elements.canvas.height);
}

// ============================================================
// FUNÇÕES DE CONEXÃO WEBSOCKET
// ============================================================

/**
 * Conecta ao servidor WebSocket
 */
function connectWebSocket() {
    updateStatus("Ligar ao WebSocket...");
    elements.connectBtn.disabled = true;
    
    WebSocketManager.connect(
        // onOpen - Chamado quando a conexão é estabelecida
        () => {
            updateStatus("Connected! Click 'Start Stream' to begin.");
            WebSocketManager.reconnectAttempts = 0;
            elements.startBtn.disabled = false;
            console.log("Ligação WebSocket estabelecida");
        },
        // onMessage - Chamado quando uma mensagem é recebida
        onWebSocketMessage,
        // onClose - Chamado quando a conexão é fechada
        (event) => {
            updateStatus(`Disconnected. Code: ${event.code}, Reason: ${event.reason || 'Unknown'}`, true);
            elements.connectBtn.disabled = false;
            elements.startBtn.disabled = true;
            elements.stopBtn.disabled = true;
            
            // Tenta reconectar automaticamente
            if (appState.streaming && WebSocketManager.reconnectAttempts < WebSocketManager.maxReconnectAttempts) {
                WebSocketManager.reconnectAttempts++;
                updateStatus(`Reconnecting (attempt ${WebSocketManager.reconnectAttempts}/${WebSocketManager.maxReconnectAttempts})...`);
                setTimeout(connectWebSocket, 2000);
            }
        },
        // onError - Chamado em caso de erro
        (error) => {
            updateStatus("Erro de ligação", true);
            console.error("Erro de WebSocket:", error);
            elements.connectBtn.disabled = false;
        }
    );
}

// ============================================================
// EXPORTAÇÃO DE MÉTRICAS
// ============================================================

/**
 * Exporta as métricas de latência para um ficheiro CSV
 */
function exportMetrics() {
    if (appState.metrics.latencyHistory.length === 0) {
        updateStatus("Sem métricas para exportar", true);
        return;
    }
    
    // Constrói o conteúdo CSV
    const csvContent = [
        ['Frame', 'T1 Captura', 'T2 Processamento', 'T3 Rede', 'T4 Descodificação', 'T5 Redndering', 'Total'],
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
    
    // Cria e descarrega o ficheiro
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `latency_metrics_${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    updateStatus("Métricas exportadas para ficheiro CSV");
}

// ============================================================
// INICIALIZAÇÃO DE EVENTOS
// ============================================================

/**
 * Inicializa os event listeners dos botões e atalhos de teclado
 */
function initializeEventListeners() {
    // Botões principais
    elements.startBtn.addEventListener('click', startStream);
    elements.stopBtn.addEventListener('click', stopStream);
    elements.connectBtn.addEventListener('click', connectWebSocket);
    elements.refreshBtn.addEventListener('click', () => location.reload());
    elements.exportBtn.addEventListener('click', exportMetrics);
    
    // ============================================================
    // ATALHOS DE TECLADO
    // ============================================================
    document.addEventListener('keydown', function(e) {
        // Espaço - Iniciar/Parar streaming
        if (e.key === ' ' || e.key === 'Spacebar') {
            e.preventDefault();
            if (appState.streaming) {
                stopStream();
            } else {
                startStream();
            }
        // C - Conectar WebSocket
        } else if (e.key === 'c' || e.key === 'C') {
            e.preventDefault();
            connectWebSocket();
        // R - Recarregar página
        } else if (e.key === 'r' || e.key === 'R') {
            e.preventDefault();
            location.reload();
        // E - Exportar métricas
        } else if (e.key === 'e' || e.key === 'E') {
            e.preventDefault();
            exportMetrics();
        }
    });
    
    // ============================================================
    // LIMPEZA AO SAIR DA PÁGINA
    // ============================================================
    window.addEventListener('beforeunload', function() {
        appState.streaming = false;
        WebSocketManager.disconnect();
    });
}

// ============================================================
// INICIALIZAÇÃO DA APLICAÇÃO
// ============================================================

/**
 * Inicializa a aplicação
 */
function initializeApp() {
    console.log("Initializing application...");
    initializeUrls();
    initializeEventListeners();
    updateStatus("Page loaded. Click 'Connect' to begin.");
    
    // Auto-conexão após 1 segundo
    setTimeout(() => {
        console.log("Auto-connecting WebSocket...");
        connectWebSocket();
    }, 1000);
}

// ============================================================
// PONTO DE ENTRADA
// ============================================================
// Inicia a aplicação quando a página termina de carregar
window.addEventListener('load', initializeApp);