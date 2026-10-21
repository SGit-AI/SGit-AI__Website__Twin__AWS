/**
 * sg-vfs-provider-indexeddb — IndexedDB-backed VFS storage provider.
 *
 * Persists files and folder metadata across page reloads using the
 * browser's IndexedDB API. Uses a single object store ("entries") keyed
 * by normalised path.
 *
 * Each entry shape:
 *   { path, type: 'file'|'folder', content?, size, created, modified }
 *
 * Parent folders are auto-created on writeFile / createFolder (mkdir -p).
 *
 * @module sg-vfs-provider-indexeddb
 * @version 0.1.0
 */

import { VfsProviderBase }  from './sg-vfs-provider-base.js';
import { normalisePath, dirname, basename, ancestors } from './sg-vfs-path.js';

const DB_NAME    = 'sg-vfs';
const DB_VERSION = 1;
const STORE      = 'entries';

export class IndexedDbProvider extends VfsProviderBase {

    /**
     * @param {object} [options]
     * @param {string} [options.dbName] — IDB database name (default: 'sg-vfs')
     * @param {string} [options.namespace] — path prefix, e.g. '/project' (default: none)
     */
    constructor(options = {}) {
        super();
        this._dbName    = options.dbName    || DB_NAME;
        this._namespace = options.namespace || '';
        /** @type {IDBDatabase|null} */
        this._db = null;
    }

    get name() { return 'indexeddb'; }

    // ── Init ─────────────────────────────────────────────────────────────

    async init() {
        this._db = await this._openDb();
        // Ensure root exists
        const root = await this._idbGet('/');
        if (!root) {
            await this._idbPut({ path: '/', type: 'folder', size: 0, created: Date.now(), modified: Date.now() });
        }
    }

    _openDb() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(this._dbName, DB_VERSION);
            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(STORE)) {
                    db.createObjectStore(STORE, { keyPath: 'path' });
                }
            };
            req.onsuccess = (e) => resolve(e.target.result);
            req.onerror   = (e) => reject(e.target.error);
        });
    }

    // ── Low-level IDB helpers ─────────────────────────────────────────────

    _tx(mode = 'readonly') {
        return this._db.transaction([STORE], mode).objectStore(STORE);
    }

    _idbGet(path) {
        return new Promise((resolve, reject) => {
            const req = this._tx('readonly').get(path);
            req.onsuccess = () => resolve(req.result ?? null);
            req.onerror   = () => reject(req.error);
        });
    }

    _idbPut(entry) {
        return new Promise((resolve, reject) => {
            const req = this._tx('readwrite').put(entry);
            req.onsuccess = () => resolve();
            req.onerror   = () => reject(req.error);
        });
    }

    _idbDelete(path) {
        return new Promise((resolve, reject) => {
            const req = this._tx('readwrite').delete(path);
            req.onsuccess = () => resolve();
            req.onerror   = () => reject(req.error);
        });
    }

    /** Return all entries whose path starts with prefix (including prefix itself). */
    _idbGetAll(prefix) {
        return new Promise((resolve, reject) => {
            const store   = this._tx('readonly');
            const results = [];
            const req     = store.openCursor();
            req.onsuccess = (e) => {
                const cursor = e.target.result;
                if (!cursor) { resolve(results); return; }
                if (cursor.key === prefix || cursor.key.startsWith(prefix === '/' ? '/' : prefix + '/')) {
                    results.push(cursor.value);
                }
                cursor.continue();
            };
            req.onerror = () => reject(req.error);
        });
    }

    // ── Entry helpers ─────────────────────────────────────────────────────

    async _assertExists(path) {
        const entry = await this._idbGet(path);
        if (!entry) throw Object.assign(new Error(`Not found: ${path}`), { code: 'ENOENT', path });
        return entry;
    }

    async _assertFile(path) {
        const entry = await this._assertExists(path);
        if (entry.type !== 'file') throw Object.assign(new Error(`Not a file: ${path}`), { code: 'EISDIR', path });
        return entry;
    }

    async _assertFolder(path) {
        const entry = await this._assertExists(path);
        if (entry.type !== 'folder') throw Object.assign(new Error(`Not a folder: ${path}`), { code: 'ENOTDIR', path });
        return entry;
    }

    async _ensureAncestors(path) {
        for (const anc of ancestors(path)) {
            const existing = await this._idbGet(anc);
            if (!existing) {
                const now = Date.now();
                await this._idbPut({ path: anc, type: 'folder', size: 0, created: now, modified: now });
            }
        }
    }

    // ── VfsProviderBase implementation ────────────────────────────────────

    async readFile(path) {
        const p     = normalisePath(path);
        const entry = await this._assertFile(p);
        return entry.content ?? '';
    }

    async writeFile(path, content) {
        const p   = normalisePath(path);
        const now = Date.now();
        await this._ensureAncestors(p);
        const existing = await this._idbGet(p);
        if (existing && existing.type === 'folder') {
            throw Object.assign(new Error(`Is a folder: ${p}`), { code: 'EISDIR', path: p });
        }
        const size = new TextEncoder().encode(content).length;
        await this._idbPut({
            path,
            type:     'file',
            content:  String(content),
            size,
            created:  existing ? existing.created : now,
            modified: now,
        });
        // Touch parent
        const parent = await this._idbGet(dirname(p));
        if (parent) { parent.modified = now; await this._idbPut(parent); }
    }

    async deleteFile(path) {
        const p = normalisePath(path);
        await this._assertFile(p);
        await this._idbDelete(p);
        const parent = await this._idbGet(dirname(p));
        if (parent) { parent.modified = Date.now(); await this._idbPut(parent); }
    }

    async listFolder(path) {
        const p = normalisePath(path);
        await this._assertFolder(p);
        const prefix = p === '/' ? '/' : p + '/';
        const all    = await this._idbGetAll(p);
        const results = [];
        for (const entry of all) {
            if (entry.path === p) continue;
            // Direct children only
            const rest = entry.path.slice(prefix.length);
            if (rest.includes('/')) continue;
            results.push({
                name:     basename(entry.path),
                path:     entry.path,
                type:     entry.type,
                size:     entry.size || 0,
                modified: entry.modified,
            });
        }
        results.sort((a, b) => {
            if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
            return a.name.localeCompare(b.name);
        });
        return results;
    }

    async stat(path) {
        const p     = normalisePath(path);
        const entry = await this._assertExists(p);
        return {
            path:     p,
            type:     entry.type,
            size:     entry.size || 0,
            created:  entry.created,
            modified: entry.modified,
        };
    }

    async createFolder(path) {
        const p = normalisePath(path);
        await this._ensureAncestors(p);
        const existing = await this._idbGet(p);
        if (!existing) {
            const now = Date.now();
            await this._idbPut({ path: p, type: 'folder', size: 0, created: now, modified: now });
        }
    }

    async copyFile(src, dst) {
        const s = normalisePath(src);
        const d = normalisePath(dst);
        const entry = await this._assertFile(s);
        await this.writeFile(d, entry.content ?? '');
    }

    async rename(src, dst) {
        const s     = normalisePath(src);
        const d     = normalisePath(dst);
        const entry = await this._assertExists(s);
        await this._ensureAncestors(d);
        await this._idbPut({ ...entry, path: d, modified: Date.now() });
        await this._idbDelete(s);
        const oldParent = await this._idbGet(dirname(s));
        if (oldParent) { oldParent.modified = Date.now(); await this._idbPut(oldParent); }
    }

    async exists(path) {
        const entry = await this._idbGet(normalisePath(path));
        return entry !== null;
    }

    /**
     * Remove all entries from the database for this provider.
     * @returns {Promise<void>}
     */
    async clear() {
        return new Promise((resolve, reject) => {
            const req = this._tx('readwrite').clear();
            req.onsuccess = async () => {
                await this._idbPut({ path: '/', type: 'folder', size: 0, created: Date.now(), modified: Date.now() });
                resolve();
            };
            req.onerror = () => reject(req.error);
        });
    }
}
