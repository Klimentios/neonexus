import * as monaco from 'monaco-editor/esm/vs/editor/editor.api.js';
import 'monaco-editor/esm/vs/basic-languages/python/python.contribution.js';
import 'monaco-editor/esm/vs/basic-languages/javascript/javascript.contribution.js';
import 'monaco-editor/esm/vs/basic-languages/typescript/typescript.contribution.js';
import 'monaco-editor/esm/vs/basic-languages/hcl/hcl.contribution.js';
import 'monaco-editor/esm/vs/basic-languages/markdown/markdown.contribution.js';
import 'monaco-editor/esm/vs/basic-languages/shell/shell.contribution.js';
import {Terminal} from '@xterm/xterm';
import {FitAddon} from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

self.MonacoEnvironment = {getWorker: () => new Worker('/static/editor.worker.js')};

const headers = () => ({'X-Session-Token': window.SESSION_TOKEN});
let editor, terminal, terminalSocket, fit, selectedPath = '', revision = null;
let active = false;
const panel = document.createElement('section');
panel.id = 'code-workspace';
panel.hidden = true;
panel.innerHTML = `
  <div class="code-toolbar"><strong>CODE WORKSPACE</strong><span id="code-root"></span><button id="code-refresh" type="button">Refresh files</button><button id="code-save" type="button" disabled>Save</button><span id="code-state"></span></div>
  <div class="code-body"><aside id="code-files" aria-label="Workspace files"></aside><div class="code-main"><div id="code-file-title">Select a file</div><div id="code-editor"></div><div class="terminal-heading"><strong>TERMINAL</strong><span>Local shell in this code workspace</span><button type="button" id="terminal-reconnect">Reconnect</button></div><div id="code-terminal"></div></div></div>`;

function state(message, error = false) {
    const el = panel.querySelector('#code-state');
    el.textContent = message;
    el.classList.toggle('error', error);
}

function language(path) {
    const ext = path.split('.').pop()?.toLowerCase();
    return ({py:'python',js:'javascript',ts:'typescript',tsx:'typescript',jsx:'javascript',
        json:'json',md:'markdown',html:'html',css:'css',scss:'scss',sh:'shell',
        tf:'hcl',go:'go',rs:'rust',java:'java',kt:'kotlin',swift:'swift',yaml:'yaml',
        yml:'yaml',sql:'sql',xml:'xml',c:'c',h:'cpp',cpp:'cpp',hpp:'cpp',asm:'assembly',s:'assembly'})[ext] || 'plaintext';
}

async function loadFiles() {
    const container = panel.querySelector('#code-files');
    container.textContent = 'Loading files…';
    try {
        const response = await fetch('/api/workspace/tree', {headers: headers()});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'File list unavailable');
        panel.querySelector('#code-root').textContent = data.root;
        container.replaceChildren();
        for (const path of data.files) {
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = path;
            button.title = path;
            button.className = path === selectedPath ? 'selected' : '';
            button.addEventListener('click', () => openFile(path));
            container.append(button);
        }
        if (data.truncated) state('Showing first 500 files');
        else if (!data.files.length) state('No text files in this workspace');
        else state('');
    } catch (error) {
        container.textContent = error.message;
        state(error.message, true);
    }
}

async function openFile(path) {
    if (editor && selectedPath && editor.getValue() !== editor.getModel()._savedText) {
        if (!confirm('Discard unsaved changes?')) return;
    }
    state('Opening…');
    try {
        const response = await fetch(`/api/workspace/file?path=${encodeURIComponent(path)}`, {headers: headers()});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Cannot open file');
        selectedPath = path;
        revision = data.revision;
        if (!editor) {
            editor = monaco.editor.create(panel.querySelector('#code-editor'), {
                value: data.content, language: language(path), theme: 'vs-dark',
                automaticLayout: true, minimap: {enabled: false}, fontSize: 13,
                scrollBeyondLastLine: false,
            });
            editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, saveFile);
            editor.onDidChangeModelContent(() => updateDirty());
        } else {
            const previous = editor.getModel();
            editor.setModel(monaco.editor.createModel(data.content, language(path)));
            previous?.dispose();
        }
        editor.getModel()._savedText = data.content;
        panel.querySelector('#code-file-title').textContent = path;
        panel.querySelectorAll('#code-files button').forEach(button => button.classList.toggle('selected', button.textContent === path));
        updateDirty();
        state('Ready');
    } catch (error) { state(error.message, true); }
}

function updateDirty() {
    panel.querySelector('#code-save').disabled = !editor || !selectedPath || editor.getValue() === editor.getModel()._savedText;
}

async function saveFile() {
    if (!editor || !selectedPath) return;
    state('Saving…');
    try {
        const response = await fetch('/api/workspace/file', {
            method: 'PUT', headers: {...headers(), 'Content-Type':'application/json'},
            body: JSON.stringify({path:selectedPath, content:editor.getValue(), revision}),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Save failed');
        revision = data.revision;
        editor.getModel()._savedText = editor.getValue();
        updateDirty();
        state('Saved');
    } catch (error) { state(error.message, true); }
}

function connectTerminal() {
    if (terminalSocket) terminalSocket.close();
    if (!terminal) {
        terminal = new Terminal({theme:{background:'#090b0d',foreground:'#e8e9e5'},fontSize:12,
            cursorBlink:true,convertEol:true,scrollback:3000});
        fit = new FitAddon();
        terminal.loadAddon(fit);
        terminal.open(panel.querySelector('#code-terminal'));
        terminal.onData(data => {
            if (terminalSocket?.readyState === WebSocket.OPEN)
                terminalSocket.send(JSON.stringify({type:'input',data}));
        });
        new ResizeObserver(() => {if (active) resizeTerminal();}).observe(panel.querySelector('#code-terminal'));
    }
    terminal.write('\r\nConnecting local terminal…\r\n');
    const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(`${scheme}//${location.host}/ws/workspace?token=${encodeURIComponent(window.SESSION_TOKEN)}`);
    terminalSocket = socket;
    socket.onopen = () => { terminal.clear(); resizeTerminal(); };
    socket.onmessage = event => terminal.write(event.data);
    socket.onclose = () => {if (terminalSocket === socket) terminal.write('\r\n[Terminal disconnected. Reconnect to start a new shell.]\r\n');};
}

function resizeTerminal() {
    if (!terminal || !active) return;
    fit.fit();
    if (terminalSocket?.readyState === WebSocket.OPEN)
        terminalSocket.send(JSON.stringify({type:'resize',cols:terminal.cols,rows:terminal.rows}));
}

function toggleWorkspace() {
    active = !active;
    panel.hidden = !active;
    document.getElementById('timeline').hidden = active;
    document.getElementById('workspace-toggle').classList.toggle('active', active);
    if (active) {
        loadFiles();
        if (!terminalSocket || terminalSocket.readyState > WebSocket.OPEN) connectTerminal();
        setTimeout(() => {editor?.layout(); resizeTerminal();}, 0);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const center = document.getElementById('center-workspace');
    if (!center) return;
    center.insertBefore(panel, center.querySelector('footer'));
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.id = 'workspace-toggle';
    toggle.className = 'settings-btn';
    toggle.textContent = 'CODE';
    toggle.title = 'Code workspace and terminal';
    toggle.addEventListener('click', toggleWorkspace);
    document.querySelector('.header-right')?.prepend(toggle);
    panel.querySelector('#code-refresh').addEventListener('click', loadFiles);
    panel.querySelector('#code-save').addEventListener('click', saveFile);
    panel.querySelector('#terminal-reconnect').addEventListener('click', connectTerminal);
});
