const { PGlite } = require('@electric-sql/pglite');
const { PGLiteSocketServer } = require('@electric-sql/pglite-socket');
const fs = require('fs');
const path = require('path');
const { unlink } = require('fs/promises');
const { existsSync } = require('fs');

const DATA_DIR = process.env.PGLITE_DATA_DIR || '/workspace/bk_cmdb_py/pglite_data';
const SOCKET_NAME = '.s.PGSQL.5432';
const SOCKET_PATH = path.join(DATA_DIR, SOCKET_NAME);

async function cleanup() {
    if (existsSync(SOCKET_PATH)) {
        try {
            await unlink(SOCKET_PATH);
            console.log(`Removed old socket at ${SOCKET_PATH}`);
        } catch (err) {
            // Ignore errors during cleanup
        }
    }
}

async function startServer() {
    try {
        // Ensure data directory exists
        if (!existsSync(DATA_DIR)) {
            fs.mkdirSync(DATA_DIR, { recursive: true });
        }

        // Clean up any existing socket
        await cleanup();

        // Create a PGlite instance
        const db = new PGlite(DATA_DIR);

        // Wait for initialization
        await db.waitReady;
        console.log('PGlite instance ready');

        // Create and start a socket server
        const server = new PGLiteSocketServer({
            db,
            path: SOCKET_PATH,
        });
        await server.start();
        console.log(`Server started on socket ${SOCKET_PATH}`);
        console.log('Authentication: disabled (trust mode)');

        // Handle graceful shutdown
        process.on('SIGINT', async () => {
            console.log('Received SIGINT, shutting down gracefully...');
            try {
                await server.stop();
                await db.close();
                console.log('Server stopped and database closed');
            } catch (err) {
                console.error('Error during shutdown:', err);
            }
            process.exit(0);
        });

        process.on('SIGTERM', async () => {
            console.log('Received SIGTERM, shutting down gracefully...');
            try {
                await server.stop();
                await db.close();
                console.log('Server stopped and database closed');
            } catch (err) {
                console.error('Error during shutdown:', err);
            }
            process.exit(0);
        });

        // Keep the process alive
        process.on('exit', () => {
            console.log('Process exiting...');
        });

    } catch (err) {
        console.error('Failed to start PGlite server:', err);
        process.exit(1);
    }
}

startServer();
