// Default settings
const defaultSettings = {
    autoScan: true,
    notifications: true,
    minMatchScore: 70,
    maxJobs: 50,
    apiEndpoint: 'http://localhost:5000'
};

// Load settings when the page opens
document.addEventListener('DOMContentLoaded', () => {
    chrome.storage.sync.get(defaultSettings, (items) => {
        document.getElementById('autoScan').checked = items.autoScan;
        document.getElementById('notifications').checked = items.notifications;
        document.getElementById('minMatchScore').value = items.minMatchScore;
        document.getElementById('maxJobs').value = items.maxJobs;
        document.getElementById('apiEndpoint').value = items.apiEndpoint;
    });
});

// Save settings
document.getElementById('save').addEventListener('click', () => {
    const settings = {
        autoScan: document.getElementById('autoScan').checked,
        notifications: document.getElementById('notifications').checked,
        minMatchScore: parseInt(document.getElementById('minMatchScore').value),
        maxJobs: parseInt(document.getElementById('maxJobs').value),
        apiEndpoint: document.getElementById('apiEndpoint').value
    };

    chrome.storage.sync.set(settings, () => {
        const status = document.getElementById('status');
        status.textContent = 'Settings saved successfully!';
        status.style.display = 'block';
        status.style.backgroundColor = '#dff0d8';
        status.style.color = '#3c763d';
        status.style.padding = '10px';
        status.style.borderRadius = '4px';

        setTimeout(() => {
            status.style.display = 'none';
        }, 2000);
    });
}); 