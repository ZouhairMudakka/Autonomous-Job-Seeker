// Run with: node --test tests/test_extension_audit.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../ui/extension/background.js'), 'utf8');

function event() {
    const callbacks = [];
    return { addListener: callback => callbacks.push(callback), fire: (...args) => callbacks.forEach(callback => callback(...args)) };
}

function harness() {
    const ports = [], commands = [], timers = new Map(), tabMessages = [];
    let stored = {}, timerId = 0;
    const chrome = {
        runtime: {
            onMessage: event(), onInstalled: event(), onStartup: event(), onSuspend: event(),
            sendMessage: (message, callback) => callback(),
            connectNative: () => {
                const connection = { onMessage: event(), onDisconnect: event(),
                    postMessage: command => commands.push(command),
                    disconnect: () => connection.onDisconnect.fire() };
                ports.push(connection);
                return connection;
            }
        },
        storage: { local: { set: (data, callback) => { stored = data; callback(); } } },
        tabs: { onUpdated: event(), query: (options, callback) => callback([]),
            sendMessage: (...args) => tabMessages.push(args) }
    };
    const context = vm.createContext({ chrome, URL, console,
        setTimeout: callback => { timers.set(++timerId, callback); return timerId; },
        clearTimeout: id => timers.delete(id) });
    vm.runInContext(source, context);
    return { chrome, ports, commands, timers, tabMessages,
        status: () => stored.automationStatus,
        request: action => { let reply; chrome.runtime.onMessage.fire({ action }, {}, value => { reply = value; }); return reply; },
        ready: (port = ports.at(-1), paused = false) => port.onMessage.fire({ type: 'statusUpdate', status: { is_running: true, is_paused: paused } }) };
}

test('worker startup connects without an installation event and reports unknown state', () => {
    const app = harness();
    assert.equal(app.ports.length, 1);
    assert.equal(app.status().connected, false);
    assert.match(app.request('start').error, /not ready/);
    assert.equal(app.commands.length, 0);
    app.chrome.runtime.onInstalled.fire();
    assert.equal(app.ports.length, 1);
});

test('only a confirmed host connection can receive a command', () => {
    const app = harness();
    app.ready();
    assert.equal(app.request('pause').status, 'command_sent');
    assert.equal(app.commands.length, 1);
    assert.equal(app.commands[0].command, 'pause');
    assert.equal(app.status().is_paused, false, 'command does not pretend host changed state');
});

test('disconnect clears stale status, schedules one reconnect, and ignores stale ports', () => {
    const app = harness();
    app.ready();
    const old = app.ports[0];
    old.onDisconnect.fire();
    old.onDisconnect.fire();
    assert.equal(app.timers.size, 1);
    assert.equal(app.request('getStatus').status.connected, false);
    const [id, reconnect] = app.timers.entries().next().value;
    app.timers.delete(id);
    reconnect();
    assert.equal(app.ports.length, 2);
    app.ready(old);
    assert.equal(app.status().connected, false);
    app.ready();
    assert.equal(app.status().connected, true);
});

test('postMessage failures report error and clear connection', () => {
    const app = harness();
    app.ready();
    app.ports[0].postMessage = () => { throw new Error('disconnected'); };
    assert.match(app.request('start').error, /could not be sent/);
    assert.equal(app.status().connected, false);
    assert.equal(app.timers.size, 1);
});

test('suspension never schedules a reconnect', () => {
    const app = harness();
    app.chrome.runtime.onSuspend.fire();
    assert.equal(app.timers.size, 0);
});

test('page updates require active automation and an actual LinkedIn hostname', () => {
    const app = harness();
    app.ready();
    app.chrome.tabs.onUpdated.fire(1, { status: 'complete' }, { url: 'https://evil.example/linkedin.com/jobs/' });
    assert.equal(app.tabMessages.length, 0);
    app.chrome.tabs.onUpdated.fire(1, { status: 'complete' }, { url: 'https://www.linkedin.com/jobs/' });
    assert.equal(app.tabMessages.length, 1);
    app.ready(undefined, true);
    app.chrome.tabs.onUpdated.fire(1, { status: 'complete' }, { url: 'https://www.linkedin.com/jobs/' });
    assert.equal(app.tabMessages.length, 1);
});
