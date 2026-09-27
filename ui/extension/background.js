/** Native messaging prototype. Commands require a status-confirmed connection.
 * Packaging still requires an extension manifest and an installed native host.
 */
let port = null;
let reconnectTimer = null;
let hostReady = false;
let suspended = false;
let latestStatus = disconnectedStatus();

function disconnectedStatus() {
    return {
        connected: false,
        is_running: false,
        is_paused: false,
        status: 'Not connected; automation state unknown',
        runtime: '--:--:--'
    };
}

// A popup or content script may not be listening. Read lastError to consume it.
function ignoreMissingReceiver() {
    void chrome.runtime.lastError;
}

function isLinkedInUrl(value) {
    try {
        const url = new URL(value);
        return url.protocol === 'https:' &&
            (url.hostname === 'linkedin.com' || url.hostname.endsWith('.linkedin.com'));
    } catch (_) {
        return false;
    }
}

function publishStatus(status) {
    latestStatus = status;
    chrome.storage.local.set({ automationStatus: status }, ignoreMissingReceiver);
    chrome.runtime.sendMessage({ action: 'statusUpdate', status }, ignoreMissingReceiver);
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs && tabs[0] && isLinkedInUrl(tabs[0].url)) {
            chrome.tabs.sendMessage(tabs[0].id, { action: 'statusUpdate', status }, ignoreMissingReceiver);
        }
    });
}

function scheduleReconnect() {
    if (!suspended && reconnectTimer === null) {
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connectToHost();
        }, 5000);
    }
}

function connectToHost() {
    if (port || suspended) return;
    if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }
    try {
        const connection = chrome.runtime.connectNative('com.linkedin.automation');
        port = connection;
        connection.onMessage.addListener((message) => {
            if (port !== connection || !message || message.type !== 'statusUpdate') return;
            const status = message.status;
            if (!status || typeof status.is_running !== 'boolean' || typeof status.is_paused !== 'boolean') return;
            hostReady = true;
            publishStatus({ ...status, connected: true });
        });
        connection.onDisconnect.addListener(() => {
            const error = chrome.runtime.lastError;
            if (error) console.warn('Native messaging host disconnected:', error.message);
            if (port !== connection) return;
            port = null;
            hostReady = false;
            publishStatus(disconnectedStatus());
            scheduleReconnect();
        });
    } catch (error) {
        port = null;
        hostReady = false;
        publishStatus(disconnectedStatus());
        scheduleReconnect();
    }
}

function sendCommand(command) {
    if (!port || !hostReady) {
        connectToHost();
        return { error: 'Native host is not ready. Retry after it connects.' };
    }
    try {
        port.postMessage({ type: 'command', command });
        // Sent is not completed: only host status updates change the UI state.
        return { status: 'command_sent' };
    } catch (error) {
        const connection = port;
        port = null;
        hostReady = false;
        try { connection.disconnect(); } catch (_) { /* Already disconnected. */ }
        publishStatus(disconnectedStatus());
        scheduleReconnect();
        return { error: 'Command could not be sent to the native host.' };
    }
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (!request || typeof request.action !== 'string') return false;
    if (['start', 'stop', 'pause'].includes(request.action)) {
        sendResponse(sendCommand(request.action));
    } else if (request.action === 'getStatus') {
        sendResponse({ status: latestStatus });
    } else {
        return false;
    }
    return false;
});

chrome.runtime.onInstalled.addListener(connectToHost);
chrome.runtime.onStartup.addListener(connectToHost);
chrome.runtime.onSuspend.addListener(() => {
    suspended = true;
    if (reconnectTimer !== null) clearTimeout(reconnectTimer);
    reconnectTimer = null;
    const connection = port;
    port = null;
    hostReady = false;
    if (connection) connection.disconnect();
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && hostReady &&
        latestStatus.is_running && !latestStatus.is_paused && isLinkedInUrl(tab.url)) {
        chrome.tabs.sendMessage(tabId, { action: 'pageUpdated', url: tab.url }, ignoreMissingReceiver);
    }
});

// Service workers restart without another installation event.
publishStatus(disconnectedStatus());
connectToHost();
