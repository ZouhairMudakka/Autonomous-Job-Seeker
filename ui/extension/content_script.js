/**
 * Content Script
 * 
 * Runs in the context of LinkedIn pages to handle direct page interactions
 * and automation tasks. 
 * 
 * In an MVP scenario, it:
 * 1) Listens for messages from background/popup (start, stop, statusUpdate, pageUpdated).
 * 2) Processes LinkedIn pages if isRunning && not isPaused.
 * 3) Optionally reads user preferences (e.g. 'autoScan') from chrome.storage.
 */

class LinkedInAutomation {
    constructor() {
        this.isRunning = false;
        this.isPaused = false;

        // (Optional) Read settings once on initialization 
        // e.g., for autoScan or maxJobs. For MVP, you can skip or enable:
        /*
        chrome.storage.sync.get(['autoScan', 'notifications', 'minMatchScore', 'maxJobs', 'apiEndpoint'], (items) => {
            this.autoScan = (items.autoScan !== undefined) ? items.autoScan : true;
            this.minMatchScore = items.minMatchScore || 70;
            this.maxJobs = items.maxJobs || 50;
            // etc.
            console.log('Loaded user settings in content script:', items);
        });
        */

        this.setupMessageListener();
    }
    
    setupMessageListener() {
        chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
            switch(request.action) {
                case 'statusUpdate':
                    this.handleStatusUpdate(request.status);
                    break;
                case 'start':
                    this.start();
                    break;
                case 'stop':
                    this.stop();
                    break;
                case 'pause':
                    // If you want a direct 'pause' action from the extension:
                    this.pauseOrResume();
                    break;
                case 'pageUpdated':
                    // If user is running, handle new page navigation
                    if (this.isRunning && !this.isPaused && request.url) {
                        this.handlePageUpdate(request.url);
                    }
                    break;
            }
            return true;
        });
    }
    
    start() {
        this.isRunning = true;
        this.isPaused = false;
        console.log('LinkedIn automation started');
        
        // Possibly handle the current page immediately
        this.handlePageUpdate(window.location.href);
    }
    
    stop() {
        this.isRunning = false;
        this.isPaused = false;
        console.log('LinkedIn automation stopped');
    }

    pauseOrResume() {
        this.isPaused = !this.isPaused;
        console.log(this.isPaused ? 'LinkedIn automation paused' : 'LinkedIn automation resumed');
        
        // If resuming, you may want to immediately process the current page
        if (!this.isPaused && this.isRunning) {
            this.handlePageUpdate(window.location.href);
        }
    }
    
    handlePageUpdate(url) {
        // Basic check for which LinkedIn page we're on:
        if (!url) url = window.location.href;

        if (url.includes('linkedin.com/in/')) {
            this.handleProfilePage();
        } else if (url.includes('linkedin.com/search/results/people')) {
            this.handleSearchPage();
        }
        // Expand with more conditions (job postings, etc.) as needed
    }
    
    handleProfilePage() {
        // Profile page automation logic
        console.log('Processing LinkedIn profile page');
        // e.g., parse user’s name, send to background or do auto-scan
        // if (this.autoScan) { ... }
    }
    
    handleSearchPage() {
        // Search results page automation logic
        console.log('Processing LinkedIn search results page');
        // e.g., list user cards, auto-click certain profiles if autoScan is true
    }
    
    handleStatusUpdate(status) {
        // Called when background.js sends a 'statusUpdate' event
        this.isRunning = status.is_running;
        this.isPaused = status.is_paused;

        // If we're running and not paused, we can re-check the page
        if (this.isRunning && !this.isPaused) {
            this.handlePageUpdate(window.location.href);
        }
    }
}

// Initialize automation once the content script loads
const automation = new LinkedInAutomation();
