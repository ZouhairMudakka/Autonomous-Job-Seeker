/**
 * Popup Interface Script
 * 
 * This script handles the popup UI interactions and communicates with
 * the background script via chrome.runtime.sendMessage.
 * 
 * It also listens for 'statusUpdate' events from the background script
 * to refresh the UI with the latest automation status.
 */

document.addEventListener('DOMContentLoaded', function() {
    const startBtn = document.getElementById('startBtn');
    const pauseBtn = document.getElementById('pauseBtn');
    const stopBtn = document.getElementById('stopBtn');
    const settingsBtn = document.getElementById('settingsBtn');
    
    const statusDiv = document.getElementById('status');
    const runtimeDiv = document.getElementById('runtime');
    const statsDiv = document.getElementById('stats');

    // On load, request current status from background
    chrome.runtime.sendMessage({ action: 'getStatus' }, function(response) {
        if (response && response.status) {
            updateDetailedStatus(response.status);
        }
    });

    // START
    startBtn.addEventListener('click', function() {
        chrome.runtime.sendMessage({ action: 'start' }, function(response) {
            console.log('Start command sent:', response);
            // We won't immediately assume success; we'll wait for a statusUpdate
        });
    });

    // PAUSE/RESUME
    pauseBtn.addEventListener('click', function() {
        // We'll send 'pause' command; the background script / Python side
        // can decide if that toggles pause/resume. 
        // Or you can do logic here to track if it's currently paused.
        chrome.runtime.sendMessage({ action: 'pause' }, function(response) {
            console.log('Pause command sent:', response);
        });
    });

    // STOP
    stopBtn.addEventListener('click', function() {
        chrome.runtime.sendMessage({ action: 'stop' }, function(response) {
            console.log('Stop command sent:', response);
        });
    });

    // SETTINGS
    settingsBtn.addEventListener('click', function() {
        chrome.runtime.openOptionsPage();
    });

    // Listen for status updates from background.js
    chrome.runtime.onMessage.addListener(function(message, sender, sendResponse) {
        if (message.action === 'statusUpdate') {
            updateDetailedStatus(message.status);
        }
    });

    /**
     * Update the popup UI with the latest status object.
     * status = {
     *   is_running: bool,
     *   is_paused: bool,
     *   status: string,
     *   runtime: string,
     *   stats: { jobs_viewed, applications } (optional)
     * }
     */
    function updateDetailedStatus(status) {
        console.log('Updating popup with status:', status);

        // 1) Update primary status text
        statusDiv.textContent = status.status || 'No status';
        let bgColor = '#f0f0f0';
        if (status.is_paused) {
            bgColor = '#fff3cd'; // paused => a light yellow
        } else if (status.is_running) {
            bgColor = '#e1f5e1'; // running => a light green
        }
        statusDiv.style.backgroundColor = bgColor;

        // 2) Update runtime
        runtimeDiv.textContent = status.runtime || '--:--:--';

        // 3) Update stats if present
        if (status.stats) {
            // e.g. status.stats.jobs_viewed, status.stats.applications
            statsDiv.textContent = `Jobs: ${status.stats.jobs_viewed} | Apps: ${status.stats.applications}`;
        } else {
            statsDiv.textContent = '';
        }

        // 4) Enable/disable buttons
        // If running => start disabled, stop enabled
        startBtn.disabled = status.is_running;
        stopBtn.disabled = !status.is_running;
        pauseBtn.disabled = !status.is_running;

        // If paused => maybe label the pauseBtn "Resume"
        if (status.is_paused) {
            pauseBtn.textContent = 'Resume';
        } else {
            pauseBtn.textContent = 'Pause';
        }

        // We might optionally disable the pauseBtn if not running
        pauseBtn.disabled = !status.is_running;
    }
});
