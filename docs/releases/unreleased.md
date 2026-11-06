# Unreleased

- Typed Python SDK: generated methods and TypedDict models for every current daemon operation, with packaged `py.typed` information.
- Explicit sessions, document/lease/CAS context, validated responses and preserved error/partial-state receipts; no implicit startup or native retry.
- Per-client certificate-verified TLS configuration and high-level workspace file upload/download through the existing transport.
