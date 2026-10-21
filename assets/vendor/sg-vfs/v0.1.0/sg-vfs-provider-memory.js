/**
 * sg-vfs-provider-memory — In-memory VFS storage provider.
 *
 * Stores all data in a JavaScript Map. Data is lost on page reload.
 * Intended for testing, temporary workspaces, and as the fast-layer
 * in a layered provider stack.
 *
 * Supports both files and folders. Parent folders are created
 * automatically on writeFile / createFolder.
 *
 * @module sg-vfs-provider-memory
 * @version 0.1.0
 */

import { VfsProviderBase } from './sg-vfs-provider-base.js';
import { normalisePath, dirname, basename, ancestors } from './sg-vfs-path.js';

/** @typedef {{ type:'file', content:string, size:number, created:number, modified:number }} MemFile */
/** @typedef {{ type:'folder', created:number, modified:number }} MemFolder */
/** @typedef {MemFile|MemFolder} MemEntry */

export class MemoryProvider extends VfsProviderBase {

    constructor() {
        super();
        /** @type {Map<string, MemEntry>} */
        this._store = new Map();
        // Root always exists
        this._store.set('/', { type: 'folder', created: Date.now(), modified: Date.now() });
    }

    get name() { return 'memory'; }

    // ── Helpers ──────────────────────────────────────────────────────────

    _get(path) {
        return this._store.get(normalisePath(path));
    }

    _assertExists(path) {
        const entry = this._get(path);
        if (!entry) throw Object.assign(new Error(`Not found: ${path}`), { code: 'ENOENT', path });
        return entry;
    }

    _assertFile(path) {
        const entry = this._assertExists(path);
        if (entry.type !== 'file') throw Object.assign(new Error(`Not a file: ${path}`), { code: 'EISDIR', path });
        return entry;
    }

    _assertFolder(path) {
        const entry = this._assertExists(path);
        if (entry.type !== 'folder') throw Object.assign(new Error(`Not a folder: ${path}`), { code: 'ENOTDIR', path });
        return entry;
    }

    /** Ensure all ancestor folders exist (mkdir -p). */
    _ensureAncestors(path) {
        for (const anc of ancestors(path)) {
            if (!this._store.has(anc)) {
                const now = Date.now();
                this._store.set(anc, { type: 'folder', created: now, modified: now });
            }
        }
    }

    // ── VfsProviderBase implementation ───────────────────────────────────

    /** @param {string} path @returns {Promise<string>} */
    async readFile(path) {
        const p = normalisePath(path);
        return this._assertFile(p).content;
    }

    /** @param {string} path @param {string} content @returns {Promise<void>} */
    async writeFile(path, content) {
        const p   = normalisePath(path);
        const now = Date.now();
        this._ensureAncestors(p);
        const existing = this._store.get(p);
        if (existing && existing.type === 'folder') {
            throw Object.assign(new Error(`Is a folder: ${p}`), { code: 'EISDIR', path: p });
        }
        this._store.set(p, {
            type:     'file',
            content:  String(content),
            size:     new TextEncoder().encode(content).length,
            created:  existing ? existing.created : now,
            modified: now,
        });
        // Update parent modified time
        const parent = dirname(p);
        const pEntry = this._store.get(parent);
        if (pEntry) pEntry.modified = now;
    }

    /** @param {string} path @returns {Promise<void>} */
    async deleteFile(path) {
        const p = normalisePath(path);
        this._assertFile(p);
        this._store.delete(p);
        const parent = dirname(p);
        const pEntry = this._store.get(parent);
        if (pEntry) pEntry.modified = Date.now();
    }

    /** @param {string} path @returns {Promise<Array>} */
    async listFolder(path) {
        const p = normalisePath(path);
        this._assertFolder(p);
        const prefix = p === '/' ? '/' : p + '/';
        const results = [];
        for (const [key, entry] of this._store) {
            if (key === p) continue;
            if (!key.startsWith(prefix)) continue;
            // Only direct children (no deeper paths)
            const rest = key.slice(prefix.length);
            if (rest.includes('/')) continue;
            results.push({
                name:     basename(key),
                path:     key,
                type:     entry.type,
                size:     entry.type === 'file' ? entry.size : 0,
                modified: entry.modified,
            });
        }
        results.sort((a, b) => {
            // Folders first, then alphabetical
            if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
            return a.name.localeCompare(b.name);
        });
        return results;
    }

    /** @param {string} path @returns {Promise<object>} */
    async stat(path) {
        const p     = normalisePath(path);
        const entry = this._assertExists(p);
        return {
            path:     p,
            type:     entry.type,
            size:     entry.type === 'file' ? entry.size : 0,
            created:  entry.created,
            modified: entry.modified,
        };
    }

    /** @param {string} path @returns {Promise<void>} */
    async createFolder(path) {
        const p = normalisePath(path);
        this._ensureAncestors(p);
        if (!this._store.has(p)) {
            const now = Date.now();
            this._store.set(p, { type: 'folder', created: now, modified: now });
        }
    }

    /** @param {string} src @param {string} dst @returns {Promise<void>} */
    async copyFile(src, dst) {
        const s = normalisePath(src);
        const d = normalisePath(dst);
        const entry = this._assertFile(s);
        await this.writeFile(d, entry.content);
    }

    /** @param {string} src @param {string} dst @returns {Promise<void>} */
    async rename(src, dst) {
        const s = normalisePath(src);
        const d = normalisePath(dst);
        const entry = this._assertExists(s);
        this._ensureAncestors(d);
        this._store.set(d, { ...entry, modified: Date.now() });
        this._store.delete(s);
        // Update old parent
        const oldParent = dirname(s);
        const op = this._store.get(oldParent);
        if (op) op.modified = Date.now();
    }

    /** @param {string} path @returns {Promise<boolean>} */
    async exists(path) {
        return this._store.has(normalisePath(path));
    }

    /**
     * Clear all stored data (useful in tests).
     * @returns {void}
     */
    clear() {
        this._store.clear();
        this._store.set('/', { type: 'folder', created: Date.now(), modified: Date.now() });
    }

    /**
     * Return the total number of entries (files + folders, including root).
     * @returns {number}
     */
    get size() {
        return this._store.size;
    }
}
