# AGENTS.md

## Cursor Cloud specific instructions

This repository is **Arcanist** (`arc`), the PHP command-line client for Phabricator. It is a
single CLI tool — there is **no server, database, or long-running service** to start. "Running the
app" means invoking `bin/arc <command>`.

### Runtime / version constraints (non-obvious)

- This checkout is from **December 2015** and is only compatible with **PHP 5.x**. Running it on
  modern PHP (7/8) causes fatal errors (e.g. `ArgumentCountError` in `PhutilErrorHandler`). The
  environment therefore uses **PHP 5.6** and makes it the default `php` (via
  `update-alternatives --set php /usr/bin/php5.6`). `bin/arc` resolves the interpreter through
  `#!/usr/bin/env php`, so the default `php` must stay 5.6 for `arc` to work.
- Required PHP extensions: `curl`, `json`, `xml` (provides `utf8_decode`), `mbstring`. All are
  installed for `php5.6`.

### libphutil dependency (non-obvious)

- `arc` requires the external **libphutil** library, which is **not vendored** in the repo and is
  git-ignored under `externals/includes/`. The standalone libphutil repo is now deprecated/empty on
  `master`, so it must be pinned to a **Dec 2015 commit** matching this Arcanist checkout:
  `14765d36f83acac0a109a047244aaa6fd8e081ea`. The startup update script clones and pins it into
  `externals/includes/libphutil`. If `arc` prints `Unable to load libphutil`, re-run that step.

### Running / testing

- Run the tool: `./bin/arc help`, `./bin/arc version`.
- Unit tests (Arcanist + libphutil self-tests): `./bin/arc unit --everything`.
  - Known non-blocking failures on this modern OS due to library micro-version drift (NOT setup
    problems, and unfixable without editing code): `PhutilURITestCase::testURIParsing` and
    `ArcanistXMLLinterTestCase::testLinter` (newer system `libxml`). ~442 tests pass.
  - Many `SKIP`s are expected: optional external linters (jshint, pyflakes, rubocop, etc.) and
    Mercurial/Subversion are not installed.
- Lint (Arcanist lints its own source): `./bin/arc lint --everything`. Add `--never-apply-patches`
  in non-interactive shells — otherwise `arc` prompts to apply auto-fixes and throws when stdin is
  not a TTY.
- `arc` is interactive by default; when piping/automating, pass non-interactive flags
  (e.g. `--never-apply-patches`) to avoid TTY-read exceptions.
- Networked workflows (`arc diff`, `arc land`, `arc call-conduit`) need a reachable Phabricator/
  Conduit server + auth token; offline `arc unit` / `arc lint` need neither.
