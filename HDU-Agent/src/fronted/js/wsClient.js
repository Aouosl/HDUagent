/**
 * 凌霄 WebSocket 客户端 - 连接、重连、消息解析
 */
window.WsClient = function(opts) {
    let ws = null;
    let reconnectTimer = null;
    let reconnectAttempts = 0;
    const MAX_RECONNECT = 10;
    const BASE_DELAY = 2000;

    function getWsUrl() {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return proto + "//" + window.location.host + "/ws/chat?token=" + encodeURIComponent(opts.token);
    }

    function scheduleReconnect() {
        if (reconnectAttempts >= MAX_RECONNECT) {
            opts.onStatus({ status: false, text: '连接失败' });
            return;
        }
        const delay = Math.min(BASE_DELAY * Math.pow(1.5, reconnectAttempts), 30000);
        reconnectTimer = setTimeout(function() {
            reconnectAttempts++;
            connect();
        }, delay);
    }

    function connect() {
        if (ws && ws.readyState === WebSocket.OPEN) return;
        opts.onStatus({ status: false, text: '连接中...' });

        try {
            ws = new WebSocket(getWsUrl());
        } catch (e) {
            scheduleReconnect();
            return;
        }

        ws.onopen = function() {
            reconnectAttempts = 0;
            opts.onStatus({ status: true, text: '在线就绪' });
        };

        ws.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                opts.onMessage(data);
            } catch (e) {
                console.warn('WsClient: 消息解析失败', e);
            }
        };

        ws.onclose = function(e) {
            if (e.code === 1008) {
                opts.onStatus({ status: false, text: '鉴权失败' });
                return;
            }
            opts.onStatus({ status: false, text: '断开连接' });
            scheduleReconnect();
        };

        ws.onerror = function() {};
    }

    function send(data) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
            return true;
        }
        return false;
    }

    function disconnect() {
        if (reconnectTimer) clearTimeout(reconnectTimer);
        if (ws) {
            ws.onclose = null;
            ws.close();
            ws = null;
        }
    }

    return { connect: connect, send: send, disconnect: disconnect };
};
