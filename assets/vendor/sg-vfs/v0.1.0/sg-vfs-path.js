/**
 * sg-vfs-path — Path utilities for the SGraph Virtual File System.
 *
 * All VFS paths are POSIX-style, absolute, starting with '/'.
 * These utilities normalise, join, and inspect paths without relying
 * on Node's path module (browser-safe).
 *
 * @module sg-vfs-path
 * @version 0.1.0
 */

/**
 * Normalise an absolute VFS path.
 * - Collapses multiple slashes.
 * - Resolves '.' and '..' segments.
 * - Always returns a string starting with '/'.
 * - Root is '/'.
 *
 * @param {string} path
 * @returns {string}
 */
export function normalisePath(path) {
    if (typeof path !== 'string') throw new TypeError('path must be a string');
    const absolute = path.startsWith('/') ? path : '/' + path;
    const parts = absolute.split('/');
    const resolved = [];
    for (const part of parts) {
        if (part === '' || part === '.') continue;
        if (part === '..') {
            resolved.pop();
        } else {
            resolved.push(part);
        }
    }
    return '/' + resolved.join('/');
}

/**
 * Join path segments into a normalised absolute path.
 *
 * @param {...string} segments
 * @returns {string}
 */
export function joinPath(...segments) {
    return normalisePath(segments.join('/'));
}

/**
 * Return the directory portion of a path (everything before the last '/').
 *
 * @param {string} path
 * @returns {string}
 */
export function dirname(path) {
    const n = normalisePath(path);
    if (n === '/') return '/';
    const idx = n.lastIndexOf('/');
    return idx === 0 ? '/' : n.slice(0, idx);
}

/**
 * Return the final component of a path (everything after the last '/').
 *
 * @param {string} path
 * @returns {string}
 */
export function basename(path) {
    const n = normalisePath(path);
    if (n === '/') return '';
    return n.slice(n.lastIndexOf('/') + 1);
}

/**
 * Return the file extension, including the dot (e.g. '.json').
 * Returns '' if there is no extension.
 *
 * @param {string} path
 * @returns {string}
 */
export function extname(path) {
    const name = basename(path);
    const dot = name.lastIndexOf('.');
    if (dot <= 0) return '';
    return name.slice(dot);
}

/**
 * Return true if `child` is equal to or inside `ancestor`.
 *
 * @param {string} ancestor
 * @param {string} child
 * @returns {boolean}
 */
export function isDescendant(ancestor, child) {
    const a = normalisePath(ancestor);
    const c = normalisePath(child);
    if (a === '/') return true;
    return c === a || c.startsWith(a + '/');
}

/**
 * Split a path into an array of segments (no empty strings, no '/').
 *
 * @param {string} path
 * @returns {string[]}
 */
export function splitPath(path) {
    const n = normalisePath(path);
    if (n === '/') return [];
    return n.slice(1).split('/');
}

/**
 * Return all ancestor paths of a given path, from root downward.
 * Does not include the path itself.
 *
 * @param {string} path
 * @returns {string[]}
 */
export function ancestors(path) {
    const segments = splitPath(path);
    const result = [];
    for (let i = 1; i < segments.length; i++) {
        result.push('/' + segments.slice(0, i).join('/'));
    }
    return result;
}

/**
 * Validate that a path is an acceptable VFS path (absolute, no null bytes).
 * Throws if invalid.
 *
 * @param {string} path
 * @returns {string} The normalised path.
 */
export function assertValidPath(path) {
    if (typeof path !== 'string') throw new TypeError('VFS path must be a string');
    if (!path.startsWith('/'))    throw new RangeError(`VFS path must be absolute: ${path}`);
    if (path.includes('\0'))      throw new RangeError(`VFS path must not contain null bytes`);
    return normalisePath(path);
}
