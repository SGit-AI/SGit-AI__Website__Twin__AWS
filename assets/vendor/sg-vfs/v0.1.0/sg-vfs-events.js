/**
 * sg-vfs-events — Event name constants for the SGraph Virtual File System.
 *
 * All VFS operations are mediated through DOM CustomEvents dispatched on a
 * [data-vfs-bus] ancestor element. Components dispatch *-request events;
 * the sg-vfs-bus headless component handles them and dispatches *-response
 * or *-error events back on the same bus.
 *
 * Every event carries a meta-envelope in its detail:
 *   { requestId, timestamp, wallTime, path, provider }
 *
 * @module sg-vfs-events
 * @version 0.1.0
 */

/** @type {Readonly<Record<string, string>>} */
export const SGL_VFS = Object.freeze({

    // ── File operations — requests ────────────────────────────────────────
    /** Read file contents. detail: { requestId, path } */
    READ_REQUEST:          'vfs:read-request',
    /** Write file contents. detail: { requestId, path, content, options? } */
    WRITE_REQUEST:         'vfs:write-request',
    /** Delete a file or empty folder. detail: { requestId, path } */
    DELETE_REQUEST:        'vfs:delete-request',
    /** List folder entries. detail: { requestId, path } */
    LIST_REQUEST:          'vfs:list-request',
    /** Stat a path (metadata). detail: { requestId, path } */
    STAT_REQUEST:          'vfs:stat-request',
    /** Create a folder (and parents). detail: { requestId, path } */
    CREATE_FOLDER_REQUEST: 'vfs:create-folder-request',
    /** Copy a file. detail: { requestId, src, dst } */
    COPY_REQUEST:          'vfs:copy-request',
    /** Rename/move a file. detail: { requestId, src, dst } */
    RENAME_REQUEST:        'vfs:rename-request',
    /** Check whether a path exists. detail: { requestId, path } */
    EXISTS_REQUEST:        'vfs:exists-request',

    // ── File operations — responses ───────────────────────────────────────
    /** Read succeeded. detail: { requestId, path, content, provider, wallTime } */
    READ_RESPONSE:          'vfs:read-response',
    /** Write succeeded. detail: { requestId, path, provider, wallTime } */
    WRITE_RESPONSE:         'vfs:write-response',
    /** Delete succeeded. detail: { requestId, path, provider, wallTime } */
    DELETE_RESPONSE:        'vfs:delete-response',
    /** List succeeded. detail: { requestId, path, entries, provider, wallTime } */
    LIST_RESPONSE:          'vfs:list-response',
    /** Stat succeeded. detail: { requestId, path, stat, provider, wallTime } */
    STAT_RESPONSE:          'vfs:stat-response',
    /** Create folder succeeded. detail: { requestId, path, provider, wallTime } */
    CREATE_FOLDER_RESPONSE: 'vfs:create-folder-response',
    /** Copy succeeded. detail: { requestId, src, dst, provider, wallTime } */
    COPY_RESPONSE:          'vfs:copy-response',
    /** Rename succeeded. detail: { requestId, src, dst, provider, wallTime } */
    RENAME_RESPONSE:        'vfs:rename-response',
    /** Exists check result. detail: { requestId, path, exists, provider, wallTime } */
    EXISTS_RESPONSE:        'vfs:exists-response',

    // ── Operation errors ──────────────────────────────────────────────────
    /** An operation failed. detail: { requestId, path?, operation, error, provider, wallTime } */
    ERROR: 'vfs:error',

    // ── Provider lifecycle ────────────────────────────────────────────────
    /** A provider was registered. detail: { provider, priority } */
    PROVIDER_REGISTERED: 'vfs:provider-registered',
    /** A provider finished initialisation. detail: { provider } */
    PROVIDER_READY:      'vfs:provider-ready',
    /** A provider encountered a non-fatal error. detail: { provider, error } */
    PROVIDER_ERROR:      'vfs:provider-error',
    /** A read was served from this provider (cache hit). detail: { provider, path, requestId } */
    PROVIDER_HIT:        'vfs:provider-hit',
    /** A read missed this provider (cache miss). detail: { provider, path, requestId } */
    PROVIDER_MISS:       'vfs:provider-miss',

    // ── Write-queue / drain (layered provider) ────────────────────────────
    /** A write was queued for async propagation. detail: { path, requestId, queueDepth } */
    WRITE_QUEUED:    'vfs:write-queued',
    /** The write queue has started draining. detail: { queueDepth } */
    DRAIN_STARTED:   'vfs:drain-started',
    /** The write queue finished draining. detail: { written, errors } */
    DRAIN_COMPLETE:  'vfs:drain-complete',

    // ── Vault commit events (vault provider only) ─────────────────────────
    /** A vault commit is starting. detail: { message, fileCount } */
    COMMIT_STARTED:  'vfs:commit-started',
    /** A vault commit completed. detail: { commitId, message, fileCount, wallTime } */
    COMMIT_COMPLETE: 'vfs:commit-complete',
    /** A vault commit failed. detail: { error, message } */
    COMMIT_ERROR:    'vfs:commit-error',
    /** A merge conflict was detected. detail: { path, localId, remoteId } */
    CONFLICT_DETECTED: 'vfs:conflict-detected',

    // ── Batch generation (sg-vfs-generator) ──────────────────────────────
    /** A batch operation sequence is starting. detail: { batchId, total, preset } */
    BATCH_STARTED:  'vfs:batch-started',
    /** Progress through a batch. detail: { batchId, done, total, lastOp } */
    BATCH_PROGRESS: 'vfs:batch-progress',
    /** A batch operation sequence completed. detail: { batchId, total, errors, wallTime } */
    BATCH_COMPLETE: 'vfs:batch-complete',
});
