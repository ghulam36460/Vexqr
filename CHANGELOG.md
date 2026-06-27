# Changelog

All notable changes to this project are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## 2.0.0

Both packages are released together at the same version.

- `aegix-core` (Python, PyPI): **2.0.0**
- `aegix-orchestrator` (TypeScript, npm/bun): **2.0.0**

### Changed
- **Renamed the project from `sentinel` to `aegix`** (the `sentinel` name was already
  taken on npm, PyPI, and bun). This affects the package names (`aegix-core`,
  `aegix-orchestrator`), the import package (`import aegix`), the CLI command (`aegix`),
  the public class (`Aegix`/`AegixOptions`/`AegixConfig`), the Java package
  (`com.aegix.perf`), the native library (`libaegix`) and C symbols (`aegix_*`), the data
  directory (`.aegix/`), and the environment variables (`AEGIX_*`).
- Bumped both packages to **2.0.0**.
- Java performance layer (`DispatchCoordinator`) rewritten to use the stable,
  non-preview virtual-thread API (`Executors.newVirtualThreadPerTaskExecutor()`),
  which compiles on **JDK 21+** with no `--enable-preview` flag. The previous code
  used `StructuredTaskScope.ShutdownOnFailure`, a preview API that fails to compile
  on current JDKs.
- Documentation corrected from "Java 26" to "Java" / "JDK 21+" to match the actual
  requirement. The `aegix accel` status line now reads `Java perf layer`.

### Added
- Full documentation set under `docs/` (getting started, architecture, CLI
  reference, configuration, publishing, production readiness).
- Root `LICENSE` (MIT) and `pycore/LICENSE`.
- `files` allowlist and `prepublishOnly` build hook in `package.json` so the npm
  tarball always ships a freshly built `dist/`.
- `*.swp` / editor-cruft patterns to `.gitignore`.

### Fixed
- Removed a committed Vim swap file (`.gitlab/duo/.mcp.json.swp`) from version control.

### Verified
- Python: 23/23 tests pass. TypeScript: 9/9 tests pass.
- `tsc` typecheck and build clean.
- C + hand-tuned Assembly accelerator builds from source; native FNV-1a hash and
  token estimator produce results identical to the pure-Python fallback.
- Java performance layer compiles to a jar on JDK 21+ with no preview flags.
- Clean `pip install` into a fresh virtualenv; `aegix` CLI runs end-to-end.
- Supervisor loop detection fires, injects a redirect, and the run completes with
  no human intervention.
- `python -m build` + `twine check` pass; `npm pack` ships the correct files.
