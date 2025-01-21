/**
 * Background Script (Native Messaging Version)
 * 
 * This script runs in the background and manages the state of the automation,
 * coordinating between the popup UI, content scripts, and the Python application
 * via Chrome native messaging.
 * 
 * Key Points:
 * - Instead of reading/writing status.json in the extension folder,
 *   we use native messaging to send commands and receive status updates.
 * - We store the latest status in chrome.storage.local so the popup or content
 *   scripts can retrieve it quickly.
 */

// In-memory state
let isRunning = false;
let isPaused = false;

// We store the Native Messaging port globally
let port = null;

// Connect to the native messaging host
function connectToHost() {
    // The host name here must match what you specified in your host manifest
    // e.g. "com.linkedin.automation"
    port = chrome.runtime.connectNative('com.linkedin.automation');

    port.onMessage.addListener((message) => {
        // Expecting a JSON object like: { type: 'statusUpdate', status: {...} }
        if (message.type === 'statusUpdate') {
            handleStatusUpdate(message.status);
        } else {
            console.log('Unknown message type:', message.type, message);
        }
    });

    port.onDisconnect.addListener(() => {
        console.log('Disconnected from native host. Retrying in 5 seconds...');
        port = null;
        setTimeout(connectToHost, 5000);
    });
}

// Handle status updates from Python
function handleStatusUpdate(status) {
    // Update internal state
    isRunning = status.is_running;
    isPaused = status.is_paused;

    // Store status in chrome.storage
    chrome.storage.local.set({ automationStatus: status }, function() {
        if (chrome.runtime.lastError) {
            console.error('Error saving status:', chrome.runtime.lastError);
        }
    });

    // Broadcast status to popup or content scripts
    chrome.runtime.sendMessage({
        action: 'statusUpdate',
        status: status
    });

    // Optionally, to notify content scripts of active tab:
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
        if (tabs && tabs[0]) {
            chrome.tabs.sendMessage(tabs[0].id, {
                action: 'statusUpdate',
                status: status
            });
        }
    });
}

// Send a command to Python (start/stop/pause, etc.)
function sendCommand(command) {
    if (port) {
        // We assume a JSON structure like { type: 'command', command: 'start' }
        port.postMessage({
            type: 'command',
            command: command
        });
    } else {
        console.error('Not connected to native host. Attempting reconnect...');
        connectToHost();
    }
}

// Listen for messages from popup/content
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    switch(request.action) {
        case 'start':
            sendCommand('start');
            sendResponse({status: 'command_sent'});
            break;

        case 'stop':
            sendCommand('stop');
            sendResponse({status: 'command_sent'});
            break;

        case 'pause':
            sendCommand('pause');
            sendResponse({status: 'command_sent'});
            break;

        case 'getStatus':
            // Return the latest status from storage
            chrome.storage.local.get(['automationStatus'], function(result) {
                sendResponse({
                    status: result.automationStatus || {
                        is_running: false,
                        is_paused: false,
                        status: 'Not connected',
                        runtime: '00:00:00'
                    }
                });
            });
            return true; // Keep channel open for async response

        default:
            sendResponse({error: 'Unknown action'});
    }
    return true;
});

// Attempt to connect when extension is installed or loaded
chrome.runtime.onInstalled.addListener(() => {
    connectToHost();
});

// If extension is reloaded or suspended, we might want to reconnect or cleanup
chrome.runtime.onSuspend.addListener(() => {
    if (port) {
        port.disconnect();
    }
});

// If you want to track tabs
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && isRunning) {
        chrome.tabs.sendMessage(tabId, {
            action: 'pageUpdated',
            url: tab.url
        });
    }
});
