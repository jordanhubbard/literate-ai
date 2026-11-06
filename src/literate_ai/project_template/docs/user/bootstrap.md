# Bootstrap Literate AI for this project

Follow this page before the first `litai` command. It works with Python's standard
library and does not install or change anything in this project.

1. Install Python 3.11 or newer and Git. From the project root, run
   `python3 scripts/bootstrap_litai.py` on POSIX or
   `py -3 scripts/bootstrap_litai.py` in native Windows PowerShell. If it reports
   `ready`, continue with `litai doctor` in the same environment.
2. If it reports `missing`, `incompatible`, or `check-unavailable`, read the printed **required
   distribution** identity from `literate.project.json`. This is the pinned
   installed-payload identity, **not** the downloadable wheel file's SHA-256.
   For `check-unavailable`, inspect the reported error: an older CLI may lack
   the version check, and a failing CLI cannot establish compatibility. Keep
   that installation intact and use the isolated path below. If the script
   reports `check-failed`, inspect the printed version-check command before
   changing runtimes. If it reports `project-invalid`, ask the maintainer to
   repair the manifest rather than guessing a pin.
   Obtain the matching Literate AI wheel and its wheel SHA-256 from the project
   maintainer or a published release. The project's identity alone cannot name
   a download URL or prove a wheel file matches; do not guess that the latest
   release satisfies an older project pin.
3. Verify the downloaded wheel against its supplied wheel SHA-256 before
   installation. On POSIX run
   `python3 scripts/bootstrap_litai.py --wheel path/to/DOWNLOADED_WHEEL.whl --wheel-sha256 HEX`;
   in native Windows PowerShell use
   `py -3 scripts\bootstrap_litai.py --wheel path\to\DOWNLOADED_WHEEL.whl --wheel-sha256 HEX`.
   If the checksum, download, or package index is unavailable, stop and request
   the matching wheel or access from the project maintainer. Do not change the
   project pin.
4. Install into an isolated environment. On POSIX:

   ```console
   python3 -m venv .litai-venv
   .litai-venv/bin/python -m pip install path/to/DOWNLOADED_WHEEL.whl
   .litai-venv/bin/python scripts/bootstrap_litai.py --litai .litai-venv/bin/litai
   ```

   In native Windows PowerShell:

   ```powershell
   py -3 -m venv .litai-venv
   .\.litai-venv\Scripts\python.exe -m pip install path\to\DOWNLOADED_WHEEL.whl
   .\.litai-venv\Scripts\python.exe scripts\bootstrap_litai.py --litai .\.litai-venv\Scripts\litai.exe
   ```

   If pip cannot resolve dependencies, preserve the environment and report the
   package-index error. Do not install into a shared Python or silently upgrade
   an existing LitAI installation. Keep `.litai-venv/` out of version control;
   a local `.git/info/exclude` entry works for a Git checkout.
5. Continue only when the check reports `ready`. Use the isolated environment's
   `litai` executable for `doctor`, `status`, and subsequent project commands.
   If a newly installed wheel still reports `incompatible`, obtain the wheel
   matching this project's pin or use the separately reviewed Standard rebind
   procedure with project-owner authorization. Bootstrap never applies a rebind.
