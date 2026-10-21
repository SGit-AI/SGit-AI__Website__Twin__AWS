/**
 * sg-vfs-provider-base — Abstract base class for VFS storage providers.
 *
 * All concrete providers (memory, IndexedDB, vault) extend this class and
 * implement the abstract methods below. The VirtualFileSystem in sg-vfs-core.js
 * calls these methods; it never accesses the underlying storage directly.
 *
 * Stat object shape:
 *   { path: string, type: 'file'|'folder', size: number,
 *     created: number, modified: number, mimeType?: string }
 *
 * Entry object shape (returned by list):
 *   { name: string, path: string, type: 'file'|'folder', size: number, modified: number }
 *
 * @module sg-vfs-provider-base
 * @version 0.1.0
 */

export class VfsProviderBase {

    /**
     * Human-readable name for this provider (used in events and logs).
     * @type {string}
     */
    get name() {
        return 'base';
    }

    /**
     * Initialise the provider (open DB connections, etc.).
     * Called once by VirtualFileSystem before any operations.
     *
     * @returns {Promise<void>}
     */
    async init() {}

    // ── Core operations ──────────────────────────────────────────────────

    /**
     * Read a file and return its content as a string.
     * Throws if the path does not exist or is a folder.
     *
     * @param {string} path — normalised absolute path
     * @returns {Promise<string>}
     */
    async readFile(path) {           // eslint-disable-line no-unused-vars
        throw new Error(`${this.name}.readFile() not implemented`);
    }

    /**
     * Write (create or overwrite) a file with string content.
     *
     * @param {string} path — normalised absolute path
     * @param {string} content
     * @param {object} [options]
     * @returns {Promise<void>}
     */
    async writeFile(path, content, options) { // eslint-disable-line no-unused-vars
        throw new Error(`${this.name}.writeFile() not implemented`);
    }

    /**
     * Delete a file. Throws if it does not exist.
     *
     * @param {string} path
     * @returns {Promise<void>}
     */
    async deleteFile(path) {         // eslint-disable-line no-unused-vars
        throw new Error(`${this.name}.deleteFile() not implemented`);
    }

    /**
     * List entries in a folder.
     * Returns [] for an empty folder. Throws if path is not a folder.
     *
     * @param {string} path
     * @returns {Promise<Array<{name:string, path:string, type:'file'|'folder', size:number, modified:number}>>}
     */
    async listFolder(path) {         // eslint-disable-line no-unused-vars
        throw new Error(`${this.name}.listFolder() not implemented`);
    }

    /**
     * Return metadata for a path.
     * Throws if the path does not exist.
     *
     * @param {string} path
     * @returns {Promise<{path:string, type:'file'|'folder', size:number, created:number, modified:number}>}
     */
    async stat(path) {               // eslint-disable-line no-unused-vars
        throw new Error(`${this.name}.stat() not implemented`);
    }

    /**
     * Create a folder (and all parent folders if needed).
     * Idempotent: does not throw if the folder already exists.
     *
     * @param {string} path
     * @returns {Promise<void>}
     */
    async createFolder(path) {       // eslint-disable-line no-unused-vars
        throw new Error(`${this.name}.createFolder() not implemented`);
    }

    /**
     * Copy a file from src to dst (overwrite dst if it exists).
     *
     * @param {string} src
     * @param {string} dst
     * @returns {Promise<void>}
     */
    async copyFile(src, dst) {       // eslint-disable-line no-unused-vars
        throw new Error(`${this.name}.copyFile() not implemented`);
    }

    /**
     * Rename/move a file from src to dst.
     *
     * @param {string} src
     * @param {string} dst
     * @returns {Promise<void>}
     */
    async rename(src, dst) {         // eslint-disable-line no-unused-vars
        throw new Error(`${this.name}.rename() not implemented`);
    }

    /**
     * Return true if the given path exists (file or folder).
     *
     * @param {string} path
     * @returns {Promise<boolean>}
     */
    async exists(path) {             // eslint-disable-line no-unused-vars
        throw new Error(`${this.name}.exists() not implemented`);
    }
}
