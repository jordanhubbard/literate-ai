# External execution placement

Acquire a fresh private workspace using the existing descriptor-backed write
reservation owner. Bind its directory identity and allocation to the exact build
request; no saved document can reconstruct its execution capability. Retire the
capability on scope exit while retaining outputs and partial work. Refuse source
overlap, aliases, substituted directories or markers and ended ownership scopes.

SDK roots remain canonical relative paths. Only explicitly selected external
builds expand `@SDK_SOURCE_ROOT@`, `@SDK_WORKSPACE_ROOT@` and `@SDK_OUTPUT_ROOT@`
inside authored command argv. Tools and environment cannot supply these slots;
unknown or incomplete slots refuse. Commands retain their original source-relative
working directories. The existing license, snapshot, native loader, authorization,
revocation and source-custody owners continue to govern production and capture.
Record actual expanded command argv and placement identity for external builds.

The public source-build service accepts a live owner. Project acquisition accepts
an optional trusted-host factory supplying one owner per selected recipe. It
creates no output workspace implicitly. Physical placement changes build
authorization identity; portable recipes, layouts and logical paths are unchanged.

Qualification must build the original native fixture with read-only source,
retire original source and outputs after protected capture, materialize a fresh
SDK and execute a real consumer. Workspace replacement, changed grants and source
or product mutation remain refusals. FreeBSD OS-SDK and retained lifecycle evidence
are separate requirements, and remain incomplete until actually exercised.
