# Publishing

Aegix ships two packages that are published to two different registries:

| Package | Registry | Command users run |
| ------- | -------- | ----------------- |
| `aegix-core` (Python) | **PyPI** | `pip install aegix-core` |
| `aegix-orchestrator` (TypeScript) | **npm** (works with bun) | `bun add aegix-orchestrator` / `npm i -g aegix-orchestrator` |

Both packages are currently at **2.0.0**. Bump the version in **both**
`pycore/pyproject.toml` and `package.json` before publishing, and tag the release in git.

> **Credentials required.** Publishing uploads to public registries and therefore needs
> credentials that are not stored in the repo: a **PyPI API token** (`twine`) and an
> **npm login/token** (`npm`/`bun`). Run the publish commands below from a machine where
> you have authenticated. The packages are fully built and validated and ready to upload.

---

## Publish the Python core to PyPI (`pip`)

### 1. One-time prerequisites

```bash
python3 -m pip install --upgrade build twine
```

Create accounts on [PyPI](https://pypi.org/) and (recommended) [TestPyPI](https://test.pypi.org/),
then create an API token for each. Configure it in `~/.pypirc` or via the
`TWINE_USERNAME=__token__` / `TWINE_PASSWORD=<token>` environment variables.

### 2. Confirm the package name is available

`aegix-core` must be unique on PyPI. Check https://pypi.org/project/aegix-core/. If
it is taken, rename the project in `pyproject.toml` (e.g. `aegix-orchestrator-core`)
before publishing.

### 3. Build the distributions

```bash
cd pycore
rm -rf dist build *.egg-info
python3 -m build            # produces dist/*.whl and dist/*.tar.gz
twine check dist/*          # validates metadata/README rendering
```

### 4. Upload to TestPyPI first (dry run)

```bash
twine upload --repository testpypi dist/*
# verify it installs cleanly from TestPyPI in a fresh venv:
python3 -m venv /tmp/t && source /tmp/t/bin/activate
pip install -i https://test.pypi.org/simple/ aegix-core
aegix --help
```

### 5. Publish to real PyPI

```bash
cd pycore
twine upload dist/*
```

Users can then:

```bash
pip install aegix-core
pip install 'aegix-core[mcp]'     # extras still work
```

> Note on native extras: `[accel]` pulls `cffi` and `jpype1`. The published wheel is
> pure-Python; the C/Assembly and Java artifacts are built locally by the user (see
> `pycore/README.md`). This keeps the wheel portable and the install step free of native
> build dependencies.

---

## Publish the TypeScript adapter to npm (works with `bun`)

`bun` publishes to and installs from the **npm registry**. There is no separate "bun
registry"; `bun publish` and `npm publish` target the same place, and `bun add` installs
npm packages.

### 1. One-time prerequisites

```bash
npm login          # or: bun pm whoami  (bun reads the same npm auth)
```

### 2. Confirm the package name is available

Check https://www.npmjs.com/package/aegix-orchestrator. If taken, either rename in
`package.json` or publish under a scope you own (recommended), e.g.
`@your-org/aegix-orchestrator`.

### 3. Make the published tarball correct

The package's `bin` points at `dist/cli/index.js`, so the build output must be included.
Build before publishing and ship only what is needed by adding to `package.json`:

```jsonc
{
  "files": ["dist", "README.md", "LICENSE"],
  "scripts": {
    "prepublishOnly": "npm run clean && npm run build"
  }
}
```

`prepublishOnly` guarantees a fresh `dist/` is built automatically on every publish.

### 4. Dry-run the package contents

```bash
npm run build
npm pack --dry-run        # lists exactly what will be published
# or with bun:
bun pm pack --dry-run
```

Confirm `dist/cli/index.js` and `dist/index.js` are present and `node_modules`/`src` are not.

### 5. Publish

```bash
# scoped public package (first publish needs --access public):
npm publish --access public
# or:
bun publish --access public
```

Users can then:

```bash
bun add @your-org/aegix-orchestrator
# or install the CLI globally
npm install -g @your-org/aegix-orchestrator
aegix run "check if my web app is secure" --dry-run
```

---

## Release checklist

- [ ] Version bumped in `pycore/pyproject.toml` **and** `package.json` (matching).
- [ ] `pytest` green (23/23) and `npm test` green (9/9).
- [ ] `npm run typecheck` and `npm run build` clean.
- [ ] `twine check dist/*` passes; `npm pack --dry-run` shows correct files.
- [ ] Published to TestPyPI and verified before real PyPI.
- [ ] `LICENSE` file present at the root (MIT is declared in metadata — see note below).
- [ ] Git tag created, e.g. `git tag v0.2.0 && git push --tags`.
