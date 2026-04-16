/**
 * CARFul - Python Bridge
 *
 * Manages communication between Electron and the Python backend
 * using stdio-based JSON-RPC protocol.
 *
 * The Python backend runs as a subprocess, receiving JSON commands
 * on stdin and sending JSON responses on stdout.
 */

const { spawn } = require('child_process');
const path = require('path');
const { app } = require('electron');

/**
 * JSON-RPC 2.0 error codes
 */
const RPC_ERRORS = {
    PARSE_ERROR: -32700,
    INVALID_REQUEST: -32600,
    METHOD_NOT_FOUND: -32601,
    INVALID_PARAMS: -32602,
    INTERNAL_ERROR: -32603,
    SERVER_ERROR: -32000,
};

/**
 * PythonBridge manages the Python subprocess and RPC communication.
 */
class PythonBridge {
    constructor() {
        this.process = null;
        this.requestId = 0;
        this.pendingRequests = new Map();
        this.buffer = '';
        this.isReady = false;
        this.pythonPath = this._findPythonPath();
        this._readyPromise = null;
        this._readyResolve = null;
        this._pendingQueue = []; // Queue for requests that arrive before ready

        this._start();
    }

    /**
     * Find the Python executable path.
     * In production, this will be the PyInstaller-bundled executable.
     */
    _findPythonPath() {
        if (process.platform === 'win32') {
            // In production, use bundled embeddable Python
            const path = require('path');
            const fs = require('fs');
            const { app } = require('electron');

            if (app.isPackaged) {
                const bundledPython = path.join(process.resourcesPath, 'python-win', 'python.exe');
                if (fs.existsSync(bundledPython)) {
                    console.log(`Using bundled Python: ${bundledPython}`);
                    return bundledPython;
                }
            }
            // Fallback to system Python in dev mode
            return 'python';
        }

        // macOS apps launched from Dock don't inherit shell PATH,
        // so we check common Python locations
        const fs = require('fs');
        const candidates = [
            '/opt/anaconda3/bin/python3',       // Anaconda default
            '/usr/local/bin/python3',           // Homebrew
            '/opt/homebrew/bin/python3',        // Homebrew Apple Silicon
            '/usr/bin/python3',                 // System Python
        ];

        for (const candidate of candidates) {
            if (fs.existsSync(candidate)) {
                console.log(`Found Python at: ${candidate}`);
                return candidate;
            }
        }

        // Fallback to PATH-based lookup
        console.warn('No Python found at known locations, falling back to python3');
        return 'python3';
    }

    /**
     * Get the arguments to launch the RPC server.
     */
    _getRpcServerArgs() {
        // Always run as module — works in both dev and production
        return ['-m', 'carful.rpc_server'];
    }

    /**
     * Start the Python subprocess.
     */
    _start() {
        const args = this._getRpcServerArgs();

        console.log(`Starting Python bridge: ${this.pythonPath} ${args.join(' ')}`);

        // Create a promise that resolves when Python sends the ready signal
        this._readyPromise = new Promise((resolve, reject) => {
            this._readyResolve = resolve;

            // Timeout after 15 seconds if Python never becomes ready
            setTimeout(() => {
                if (!this.isReady) {
                    console.error('Python process failed to become ready within 15 seconds');
                    reject(new Error('Python process startup timeout'));
                    // Reject all queued requests
                    for (const { reject: qReject } of this._pendingQueue) {
                        qReject(new Error('Python process startup timeout'));
                    }
                    this._pendingQueue = [];
                }
            }, 15000);
        });

        try {
            // In production, carful package is in Contents/Resources/carful/
            // In dev, it's at ../../../ (project root's parent has carful/)
            const isDev = !app.isPackaged;
            const cwd = isDev
                ? path.join(__dirname, '../../../')
                : process.resourcesPath;

            console.log(`Python CWD: ${cwd}`);

            this.process = spawn(this.pythonPath, args, {
                stdio: ['pipe', 'pipe', 'pipe'],
                cwd: cwd,
            });

            // Handle stdout (RPC responses)
            this.process.stdout.on('data', (data) => {
                this._handleData(data.toString());
            });

            // Handle stderr (logging/errors)
            this.process.stderr.on('data', (data) => {
                console.error('Python stderr:', data.toString().trim());
            });

            // Handle process exit
            this.process.on('exit', (code, signal) => {
                console.log(`Python process exited with code ${code}, signal ${signal}`);
                this.isReady = false;

                // Reject all pending requests
                for (const [id, { reject }] of this.pendingRequests) {
                    reject(new Error('Python process terminated'));
                }
                this.pendingRequests.clear();

                // Reject all queued requests
                for (const { reject } of this._pendingQueue) {
                    reject(new Error('Python process terminated'));
                }
                this._pendingQueue = [];
            });

            // Handle process error
            this.process.on('error', (error) => {
                console.error('Python process error:', error);
                this.isReady = false;
            });

            // NOT setting isReady = true here — we wait for the ready signal from Python

        } catch (error) {
            console.error('Failed to start Python process:', error);
            throw error;
        }
    }

    /**
     * Handle data received from Python stdout.
     * Parses JSON-RPC responses and resolves pending promises.
     */
    _handleData(data) {
        this.buffer += data;

        // Try to parse complete JSON messages (newline-delimited)
        const lines = this.buffer.split('\n');
        this.buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
            if (!line.trim()) continue;

            try {
                const response = JSON.parse(line);
                this._handleResponse(response);
            } catch (error) {
                console.error('Failed to parse Python response:', line, error);
            }
        }
    }

    /**
     * Handle a parsed RPC response.
     */
    _handleResponse(response) {
        const { id, result, error, method } = response;

        // Check for ready signal from Python
        if (method === 'ready') {
            console.log('Python process is ready');
            this.isReady = true;
            if (this._readyResolve) {
                this._readyResolve();
            }
            // Flush queued requests
            this._flushQueue();
            return;
        }

        if (id === undefined || id === null) {
            // Notification (no id) - could be progress update
            if (method === 'progress') {
                // Handle progress notification
                console.log('Progress:', response.params);
            }
            return;
        }

        const pending = this.pendingRequests.get(id);
        if (!pending) {
            console.warn('Received response for unknown request:', id);
            return;
        }

        this.pendingRequests.delete(id);

        if (error) {
            pending.reject(new Error(error.message || 'RPC error'));
        } else {
            pending.resolve(result);
        }
    }

    /**
     * Flush queued requests that arrived before Python was ready.
     */
    _flushQueue() {
        console.log(`Flushing ${this._pendingQueue.length} queued RPC requests`);
        const queue = [...this._pendingQueue];
        this._pendingQueue = [];

        for (const { method, params, resolve, reject } of queue) {
            this.invoke(method, params).then(resolve).catch(reject);
        }
    }

    /**
     * Send an RPC request to Python and return a Promise.
     *
     * @param {string} method - RPC method name
     * @param {object} params - Method parameters
     * @returns {Promise<any>} - Response result
     */
    invoke(method, params = {}) {
        return new Promise((resolve, reject) => {
            if (!this.process) {
                reject(new Error('Python process not started'));
                return;
            }

            // If not ready yet, queue the request
            if (!this.isReady) {
                console.log(`Python not ready yet, queuing request: ${method}`);
                this._pendingQueue.push({ method, params, resolve, reject });
                return;
            }

            const id = ++this.requestId;
            const request = {
                jsonrpc: '2.0',
                id,
                method,
                params,
            };

            // Store pending request
            this.pendingRequests.set(id, { resolve, reject });

            // Set timeout for request
            const timeout = setTimeout(() => {
                if (this.pendingRequests.has(id)) {
                    this.pendingRequests.delete(id);
                    reject(new Error(`RPC timeout for method: ${method}`));
                }
            }, 30000); // 30 second timeout

            // Update pending to clear timeout on response
            this.pendingRequests.set(id, {
                resolve: (result) => {
                    clearTimeout(timeout);
                    resolve(result);
                },
                reject: (error) => {
                    clearTimeout(timeout);
                    reject(error);
                },
            });

            // Send request
            try {
                this.process.stdin.write(JSON.stringify(request) + '\n');
            } catch (error) {
                this.pendingRequests.delete(id);
                clearTimeout(timeout);
                reject(error);
            }
        });
    }

    /**
     * Wait for the Python process to be ready.
     * @returns {Promise<void>}
     */
    waitForReady() {
        if (this.isReady) return Promise.resolve();
        return this._readyPromise;
    }

    /**
     * Shutdown the Python subprocess gracefully.
     */
    shutdown() {
        if (this.process) {
            console.log('Shutting down Python bridge...');

            // Send shutdown command
            try {
                this.process.stdin.write(JSON.stringify({
                    jsonrpc: '2.0',
                    id: 0,
                    method: 'shutdown',
                    params: {},
                }) + '\n');
            } catch (error) {
                // Ignore write errors during shutdown
            }

            // Give it a moment to shutdown gracefully
            setTimeout(() => {
                if (this.process) {
                    this.process.kill();
                    this.process = null;
                }
            }, 1000);
        }
    }
}

module.exports = { PythonBridge, RPC_ERRORS };
