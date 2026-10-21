/**
 * sg-vfs-provider-layered — Multi-provider layered VFS coordinator.
 *
 * Implements a tiered storage strategy. Providers are registered with a
 * priority (lower number = faster / checked first). The typical stack is:
 *
 *   Priority 0 — MemoryProvider     (in-process cache, ns latency)
 *   Priority 1 — IndexedDbProvider  (persistent local cache, <1ms)
 *   Priority 2 — VaultProvider      (authoritative remote, 50–500ms)
 *
 * Read strategy (waterfall):
 *   Try each provider in priority order. On the first hit return the result
 *   and back-fill all higher-priority (faster) layers asynchronously.
 *   Emit PROVIDER_HIT / PROVIDER_MISS events on the bus for each layer.
 *
 * Write strategy (write-through):
 *   Write to all providers simultaneously. All writes must succeed before
 *   the operation resolves. (Future: write-back mode with queue.)
 *
 * Delete / rename / copy:
 *   Applied to all providers (best-effort; errors are collected).
 *
 * The LayeredProvider itself extends VfsProviderBase, so it can be passed
 * directly to VirtualFileSystem as the single provider.
 *
 * @module sg-vfs-provider-layered
 * @version 0.1.0
 */

import { VfsProviderBase }  from './sg-vfs-provider-base.js';
import { SGL_VFS }          from './sg-vfs-events.js';
import { normalisePath }    from './sg-vfs-path.js';

export class LayeredProvider extends VfsProviderBase {

    /**
     * @param {object} [options]
     * @param {Element|null} [options.bus] — bus element for PROVIDER_HIT/MISS events
     */
    constructor(options = {}) {
        super();
        /** @type {Array<{ priority: number, provider: VfsProviderBase }>} */
        this._layers = [];
        this._bus    = options.bus || null;
    }

    get name() { return 'layered'; }

    /**
     * Register a storage provider at a given priority.
     * Lower priority = checked first (faster layers get lower numbers).
     *
     * @param {VfsProviderBase} provider
     * @param {number} priority
     */
    addProvider(provider, priority) {
        this._layers.push({ priority, provider });
        this._layers.sort((a, b) => a.priority - b.priority);
    }

    /** @returns {Array<{ priority: number, provider: VfsProviderBase }>} */
    get layers() { return this._layers; }

    /** Attach a bus element (used for PROVIDER_HIT/MISS events). */
    setBus(bus) { this._bus = bus; }

    // ── Lifecycle ─────────────────────────────────────────────────────────

    async init() {
        await Promise.all(this._layers.map(l => l.provider.init()));
    }

    // ── Bus helpers ───────────────────────────────────────────────────────

    _emitHit(providerName, path, requestId) {
        if (!this._bus) return;
        this._bus.dispatchEvent(new CustomEvent(SGL_VFS.PROVIDER_HIT, {
            detail:   { provider: providerName, path, requestId },
            bubbles:  true,
            composed: true,
        }));
    }

    _emitMiss(providerName, path, requestId) {
        if (!this._bus) return;
        this._bus.dispatchEvent(new CustomEvent(SGL_VFS.PROVIDER_MISS, {
            detail:   { provider: providerName, path, requestId },
            bubbles:  true,
            composed: true,
        }));
    }

    // ── Read (waterfall) ──────────────────────────────────────────────────

    async readFile(path, opts = {}) {
        const p = normalisePath(path);
        for (let i = 0; i < this._layers.length; i++) {
            const { provider } = this._layers[i];
            try {
                const content = await provider.readFile(p);
                this._emitHit(provider.name, p, opts.requestId);
                // Back-fill faster layers (async, don't await)
                this._backfill(i, p, content);
                return content;
            } catch {
                this._emitMiss(provider.name, p, opts.requestId);
            }
        }
        throw Object.assign(new Error(`Not found: ${p}`), { code: 'ENOENT', path: p });
    }

    /** Write `content` into all layers with index < hitIndex (faster layers). */
    _backfill(hitIndex, path, content) {
        for (let i = 0; i < hitIndex; i++) {
            this._layers[i].provider.writeFile(path, content).catch(() => {/* best-effort */});
        }
    }

    // ── Write (write-through all layers) ─────────────────────────────────

    async writeFile(path, content, opts = {}) {
        const p = normalisePath(path);
        await Promise.all(this._layers.map(l => l.provider.writeFile(p, content, opts)));
    }

    async deleteFile(path) {
        const p = normalisePath(path);
        const results = await Promise.allSettled(this._layers.map(l => l.provider.deleteFile(p)));
        // Succeed if at least one layer succeeded; throw the first error otherwise
        const failure = results.find(r => r.status === 'rejected');
        const success = results.find(r => r.status === 'fulfilled');
        if (!success) throw failure.reason;
    }

    // ── Folder ops (write to all) ─────────────────────────────────────────

    async listFolder(path) {
        const p = normalisePath(path);
        // Use the first layer that has the folder
        for (const { provider } of this._layers) {
            try {
                return await provider.listFolder(p);
            } catch { /* miss */ }
        }
        throw Object.assign(new Error(`Not found: ${p}`), { code: 'ENOENT', path: p });
    }

    async stat(path) {
        const p = normalisePath(path);
        for (const { provider } of this._layers) {
            try {
                return await provider.stat(p);
            } catch { /* miss */ }
        }
        throw Object.assign(new Error(`Not found: ${p}`), { code: 'ENOENT', path: p });
    }

    async createFolder(path) {
        const p = normalisePath(path);
        await Promise.all(this._layers.map(l => l.provider.createFolder(p).catch(() => {})));
    }

    async copyFile(src, dst) {
        const s = normalisePath(src);
        const d = normalisePath(dst);
        // Read from fastest available layer, then write-through
        const content = await this.readFile(s);
        await this.writeFile(d, content);
    }

    async rename(src, dst) {
        const s = normalisePath(src);
        const d = normalisePath(dst);
        await Promise.all(this._layers.map(l => l.provider.rename(s, d).catch(() => {})));
    }

    async exists(path) {
        const p = normalisePath(path);
        for (const { provider } of this._layers) {
            try {
                if (await provider.exists(p)) return true;
            } catch { /* miss */ }
        }
        return false;
    }

    // ── Introspection ─────────────────────────────────────────────────────

    /**
     * Return a summary of all registered providers.
     * @returns {Array<{ name: string, priority: number }>}
     */
    summary() {
        return this._layers.map(l => ({ name: l.provider.name, priority: l.priority }));
    }
}
