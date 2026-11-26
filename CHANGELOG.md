# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.4] - 2026-11-27

### Fixed
- `--lang` help now lists the full precedence (EXTRACTSCORE_LANG, then LC_ALL/LC_MESSAGES/LANG)

## [0.1.3] - 2026-11-27

### Changed
- README: PyPI install guidance updated

## [0.1.2] - 2026-11-14

### Fixed
- English output now says "(1 document)" instead of "(1 documents)" when a run has a single document.

## [0.1.1] - 2026-11-14

### Fixed
- Input files and config files (JSON, TOML) that start with a UTF-8 BOM are now read correctly instead of mis-scoring the first document or failing with exit code 2.

## [0.1.0] - 2026-11-14

### Added
- Field-level scoring of LLM-extracted JSON against a gold JSONL: per-field TP/FP/FN, precision, recall, F1, micro and macro aggregates.
- Error categories: `wrong_value`, `type_error`, `missing`, `hallucinated`, `parse_failure`.
- Typed comparators (`number`, `date`, `text`, `id`, `enum`, `bool`) with conservative type inference; ids and amounts are exact by default, fuzzy text matching only where configured.
- Order-independent pairing of object lists (Hungarian algorithm, pure Python), multiset comparison of scalar lists, nested lists.
- `diff` between two runs: per-field change, improved / regressed / same, and the documents whose fields flipped.
- CLI `extractscore score | diff | demo` with table, JSON and Markdown output, CI gates (`--min-f1`, `--field-min`, `--fail-on-regression`) and exit codes 0 / 1 / 2.
- English and Korean output (`--lang`, `EXTRACTSCORE_LANG`, `LC_ALL`/`LC_MESSAGES`/`LANG`).
- TOML or JSON field-rule configuration; `ignore = true` fields are reported as skipped.
- Python API: `evaluate`, `evaluate_files`, `compare`, `diff`, `check_gates`, `Config`, `FieldRule`, `load_jsonl`.
- Bundled practice mock (hand-written predictions, no model is called): `extractscore demo`, `demo --export DIR`.
- Zero runtime dependencies; Python 3.11 or newer.

[Unreleased]: https://github.com/LeeGyeongPil/extractscore/compare/v0.1.4...HEAD
[0.1.4]: https://github.com/LeeGyeongPil/extractscore/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/LeeGyeongPil/extractscore/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/LeeGyeongPil/extractscore/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/LeeGyeongPil/extractscore/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/LeeGyeongPil/extractscore/releases/tag/v0.1.0
