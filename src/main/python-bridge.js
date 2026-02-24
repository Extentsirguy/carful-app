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

        this._start();
    }

    /**
     * Find the Python executable path.
     * In production, this will be the PyInstaller-bundled executable.
     */
    _findPythonPath() {
        const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

        if (isDev) {
            // Development: use system Python
            return process.platform === 'win32' ? 'python' : 'python3';
        } else {
            // Production: use bundled executable
            const resourcesPath = process.resourcesPath;
            const execName = process.platform === 'win32' ? 'carful.exe' : 'carful';
            return path.join(resourcesPath, 'python', execName);
        }
    }

    /**
     * Get the arguments to launch the RPC server.
     */
    _getRpcServerArgs() {
        const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

        if (isDev) {
            // Development: run as Python module so carful package is importable
            return ['-m', 'carful.rpc_server'];
        } else {
            // Production: the RPC server is bundled in the executable
            return [];
        }
    }

    /**
     * Start the Python subprocess.
     */
    _start() {
        const args = this._getRpcServerArgs();

        console.log(`Starting Python bridge: ${this.pythonPath} ${args.join(' ')}`);

        try {
            this.process = spawn(this.pythonPath, args, {
                stdio: ['pipe', 'pipe', 'pipe'],
                cwd: path.join(__dirname, '../../../'),
            });

            // Handle stdout (RPC responses)
            this.process.stdout.on('data', (data) => {
                this._handleData(data.toString());
            });

            // Handle stderr (logging/errors)
            this.process.stderr.on('data', (data) => {
                console.error('Python stderr:', data.toString());
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
            });

            // Handle process error
            this.process.on('error', (error) => {
                console.error('Python process error:', error);
                this.isReady = false;
            });

            this.isReady = true;
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
        const { id, result, error } = response;

        if (id === undefined || id === null) {
            // Notification (no id) - could be progress update
            if (response.method === 'progress') {
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
     * Send an RPC request to Python and return a Promise.
     *
     * @param {string} method - RPC method name
     * @param {object} params - Method parameters
     * @returns {Promise<any>} - Response result
     */
    invoke(method, params = {}) {
        return new Promise((resolve, reject) => {
            if (!this.isReady || !this.process) {
                reject(new Error('Python process not ready'));
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
