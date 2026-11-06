# Next SWCLI release

- Windows background daemon startup uses the same installation's `pythonw.exe`
  so the resident daemon and COM worker do not open a console window. Startup
  diagnostics remain in the daemon log.
- The Windows notification icon uses MacSW's purple cube artwork, packaged at
  native Windows icon sizes.
- Left-clicking the icon has no action. Right-click and select **查看状态** to
  open runtime status; stop and hide remain in the same menu.

These changes are on the development branch, separate from the frozen
`v0.2.1` release. Windows validation attached an existing user SW and preserved
its process/window; the daemon and COM worker ran as `pythonw.exe` and the
custom icon registered successfully. No new SW or document edit was needed.

- MCP `execute` returns PNG previews for render results and original CAD export
  bytes as embedded resources. `include_content` is negotiated with the daemon;
  metadata-only mode and older-daemon fallback preserve the original operation.
  The raw-byte limit is 8 MiB; size/hash and delivery status are explicit.
  CAD success is retained when an attachment cannot be delivered.
