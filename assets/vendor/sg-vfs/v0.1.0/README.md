# sg-vfs v0.1.0, vendored

Copied unchanged from SGraph-AI__Tools (https://github.com/the-cyber-boardroom/SGraph-AI__Tools),
`sgraph_ai_tools__static/core/sg-vfs/v0/v0.1/v0.1.0/`, at commit a905a5c (2026-09-01), served on
https://tools.sgraph.ai/core/sg-vfs/v0/v0.1/v0.1.0/. Apache-2.0, the same licence as this site's code.

Used by `s3/index.html`: the Python twin keeps its buckets in a memory provider with a change
journal, and the page writes each change through to `IndexedDbProvider`, so a reload restores
them. That is the layered provider's write-through (memory at priority 0, IndexedDB at 1),
done across the Python and JavaScript boundary. A vault provider at priority 2 is the plan
both projects share.

Files: sg-vfs-provider-base.js, sg-vfs-path.js, sg-vfs-provider-indexeddb.js,
sg-vfs-provider-memory.js, sg-vfs-provider-layered.js, sg-vfs-events.js. Do not edit here;
update by copying a newer version into its own folder.
