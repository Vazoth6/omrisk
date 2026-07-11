/**
 * Módulo de gestão da conexão WebSocket
 * 
 * Este módulo encapsula toda a lógica de conexão WebSocket, incluindo:
 * - Estabelecimento de conexão
 * - Gestão de reconexões
 * - Envio e receção de mensagens
 * - Verificação do estado da conexão
 */

// ============================================================
// GESTOR DE CONEXÃO WEBSOCKET
// ============================================================
const WebSocketManager = {
    // ============================================================
    // PROPRIEDADES
    // ============================================================
    connection: null,              // Objeto WebSocket atual
    reconnectAttempts: 0,          // Número de tentativas de reconexão
    maxReconnectAttempts: 10,      // Número máximo de tentativas de reconexão
    
    // ============================================================
    // MÉTODO: CONECTAR
    // ============================================================
    /**
     * Estabelece uma conexão WebSocket com o servidor
     * 
     * @param {Function} onOpenCallback - Função chamada quando a conexão é aberta
     * @param {Function} onMessageCallback - Função chamada quando uma mensagem é recebida
     * @param {Function} onCloseCallback - Função chamada quando a conexão é fechada
     * @param {Function} onErrorCallback - Função chamada em caso de erro
     * @returns {WebSocket} Objeto WebSocket criado
     */
    connect(onOpenCallback, onMessageCallback, onCloseCallback, onErrorCallback) {
        // ============================================================
        // DETERMINAÇÃO DO PROTOCOLO E URL
        // ============================================================
        // Se a página está em HTTPS, usa WSS (WebSocket seguro), caso contrário WS
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsHost = window.location.hostname;  // Endereço do servidor
        const wsUrl = `${wsProtocol}//${wsHost}:3001`;  // Porta 3001 para WebSocket
        
        console.log("Ligar ao WebSocket:", wsUrl);
        
        // ============================================================
        // CRIAÇÃO DA CONEXÃO WEBSOCKET
        // ============================================================
        this.connection = new WebSocket(wsUrl);
        
        // ============================================================
        // EVENTO: CONEXÃO ABERTA
        // ============================================================
        this.connection.onopen = function() {
            console.log("Ligação WebSocket aberta");
            if (onOpenCallback) onOpenCallback();
        };
        
        // ============================================================
        // EVENTO: MENSAGEM RECEBIDA
        // ============================================================
        this.connection.onmessage = async function(event) {
            if (onMessageCallback) await onMessageCallback(event);
        };
        
        // ============================================================
        // EVENTO: CONEXÃO FECHADA
        // ============================================================
        this.connection.onclose = function(event) {
            console.log("Ligação WebSocket fechada:", event);
            if (onCloseCallback) onCloseCallback(event);
        };
        
        // ============================================================
        // EVENTO: ERRO
        // ============================================================
        this.connection.onerror = function(error) {
            console.error("Erro no WebSocket:", error);
            if (onErrorCallback) onErrorCallback(error);
        };
        
        return this.connection;
    },
    
    /**
     * Fecha a conexão WebSocket ativa
     */
    disconnect() {
        // Verifica se existe conexão e está aberta
        if (this.connection && this.connection.readyState === WebSocket.OPEN) {
            this.connection.close();  // Fecha a conexão
        }
        this.connection = null;  // Limpa a referência
    },
    
    /**
     * Envia uma mensagem através da conexão WebSocket
     * 
     * @param {Object} message - Objeto/mensagem a enviar (será convertido para JSON)
     * @returns {boolean} true se a mensagem foi enviada, false caso contrário
     */
    send(message) {
        // Verifica se a conexão existe e está aberta
        if (this.connection && this.connection.readyState === WebSocket.OPEN) {
            this.connection.send(JSON.stringify(message));  // Converte para JSON e envia
            return true;  // Sucesso
        }
        return false;  // Falha - conexão não disponível
    },
    
    /**
     * Verifica se a conexão WebSocket está ativa
     * 
     * @returns {boolean} true se a conexão estiver aberta, false caso contrário
     */
    isConnected() {
        return this.connection && this.connection.readyState === WebSocket.OPEN;
    },
    
    /**
     * Obtém o estado atual da conexão WebSocket
     * 
     * @returns {number} Estado da conexão (0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED, -1=null)
     */
    getState() {
        return this.connection ? this.connection.readyState : -1;
    }
};