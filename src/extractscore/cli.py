"""Command line: ``extractscore score | diff | demo``.

Exit codes: 0 ok, 1 gate failed (``--min-f1``, ``--field-min``, ``--fail-on-regression``),
2 usage or input error.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import typing
from pathlib import Path
from typing import Sequence

from . import __version__
from .config import Config
from .diff import diff as diff_reports
from .errors import ExtractScoreError, InputError
from .gate import check_gates
from .i18n import LANGS, ref, resolve_lang, t
from .render import diff_markdown, diff_text, report_markdown, report_text
from .score import evaluate_files

SAMPLE_DIR = Path(__file__).resolve().parent / "sample"


def _early_lang(argv: Sequence[str]) -> str | None:
    """Find ``--lang`` before the parser exists, so the help text itself can be translated."""
    for i, arg in enumerate(argv):
        if arg == "--lang" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--lang="):
            return arg.split("=", 1)[1]
    return None


_KIND_WORDS = {"int": "int", "float": "float"}


def _translate_argparse(message: str, lang: str) -> str:
    """Translate argparse's own English messages (it has no translation hook)."""
    if lang == "en":
        return message
    patterns = (
        (r"the following arguments are required: (?P<names>.+)", "ap_required"),
        (r"unrecognized arguments: (?P<names>.+)", "ap_unrecognized"),
        (r"invalid choice: (?P<value>.+?) \(choose from (?P<choices>[^)]+)\)(?:, maybe you meant .+)?", "ap_invalid_choice"),
        (r"invalid (?P<kind>\w+) value: (?P<value>.+)", "ap_invalid_value"),
        (r"expected one argument", "ap_expected_one"),
    )
    named = re.fullmatch(r"argument (?P<name>[^:]+): (?P<rest>.+)", message, re.S)
    if named:
        return t(lang, "ap_argument", name=named["name"], message=_translate_argparse(named["rest"], lang))
    for pattern, key in patterns:
        found = re.fullmatch(pattern, message, re.S)
        if found:
            return t(lang, key, **found.groupdict())
    return message


def _make_parser_class(lang: str) -> type[argparse.ArgumentParser]:
    """An ArgumentParser whose usage prefix, group titles and usage errors follow ``lang``."""

    class Formatter(argparse.HelpFormatter):
        def add_usage(self, usage, actions, groups, prefix=None):  # type: ignore[no-untyped-def]
            super().add_usage(usage, actions, groups, t(lang, "usage_prefix") if prefix is None else prefix)

    class Parser(argparse.ArgumentParser):
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            kwargs.setdefault("formatter_class", Formatter)
            kwargs["add_help"] = False
            super().__init__(*args, **kwargs)
            self._positionals.title = t(lang, "title_positional")
            self._optionals.title = t(lang, "title_options")
            self.add_argument("-h", "--help", action="help", default=argparse.SUPPRESS, help=t(lang, "help_help"))

        def error(self, message: str) -> typing.NoReturn:
            self.print_usage(sys.stderr)
            self.exit(2, f"{self.prog}: {t(lang, 'ap_error')}: {_translate_argparse(message, lang)}\n")

    return Parser


def build_parser(lang: str) -> argparse.ArgumentParser:
    """Build the argparse parser with all help text in ``lang``."""
    parser_class = _make_parser_class(lang)
    lang_parent = argparse.ArgumentParser(add_help=False)
    lang_parent.add_argument("--lang", choices=LANGS, default=argparse.SUPPRESS, help=t(lang, "help_lang"))

    parser = parser_class(prog="extractscore", description=t(lang, "help_description"), parents=[lang_parent])
    parser.add_argument("--version", action="version", version=f"extractscore {__version__}", help=t(lang, "help_version"))
    sub = parser.add_subparsers(dest="command", required=True, metavar="{score,diff,demo}", title=t(lang, "title_commands"), parser_class=parser_class)

    score = sub.add_parser("score", help=t(lang, "help_score"), description=t(lang, "help_score"), parents=[lang_parent])
    score.add_argument("gold", help=t(lang, "help_gold"))
    score.add_argument("pred", help=t(lang, "help_pred"))
    _common(score, lang)
    score.add_argument("--min-f1", type=float, metavar="X", help=t(lang, "help_min_f1"))
    score.add_argument("--field-min", action="append", default=[], metavar="PATH=X", help=t(lang, "help_field_min"))
    score.add_argument("--top", type=int, default=5, metavar="N", help=t(lang, "help_top"))

    diff = sub.add_parser("diff", help=t(lang, "help_diff"), description=t(lang, "help_diff"), parents=[lang_parent])
    diff.add_argument("gold", help=t(lang, "help_gold"))
    diff.add_argument("pred_a", metavar="A", help=t(lang, "help_pred_a"))
    diff.add_argument("pred_b", metavar="B", help=t(lang, "help_pred_b"))
    _common(diff, lang)
    diff.add_argument("--fail-on-regression", action="store_true", help=t(lang, "help_fail_regress"))
    diff.add_argument("--tolerance", type=float, default=0.0, metavar="X", help=t(lang, "help_tolerance"))

    demo = sub.add_parser("demo", help=t(lang, "help_demo"), description=t(lang, "help_demo"), parents=[lang_parent])
    demo.add_argument("--export", metavar="DIR", help=t(lang, "help_export"))
    return parser


def _common(p: argparse.ArgumentParser, lang: str) -> None:
    p.add_argument("--config", metavar="FILE", help=t(lang, "help_config"))
    p.add_argument("--id-key", default="id", metavar="KEY", help=t(lang, "help_id_key"))
    p.add_argument("--format", choices=("table", "json", "md"), default="table", help=t(lang, "help_format"))
    p.add_argument("--out", metavar="FILE", help=t(lang, "help_out"))


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point; returns the process exit code."""
    args_list = list(sys.argv[1:] if argv is None else argv)
    lang = resolve_lang(_early_lang(args_list))
    parser = build_parser(lang)
    args = parser.parse_args(args_list)
    lang = resolve_lang(getattr(args, "lang", None))
    try:
        if args.command == "score":
            return _cmd_score(args, lang)
        if args.command == "diff":
            return _cmd_diff(args, lang)
        return _cmd_demo(args, lang)
    except ExtractScoreError as exc:
        print(f"{t(lang, 'error_prefix')}: {exc.localized(lang)}", file=sys.stderr)
        return 2


# ------------------------------------------------------------------ commands
def _load_config(path: str | None) -> Config:
    return Config.from_file(path) if path else Config()


def _parse_field_min(items: Sequence[str]) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in items:
        path, sep, value = item.rpartition("=")
        try:
            number = float(value)
        except ValueError:
            number = -1.0
        if not sep or not path or not 0.0 <= number <= 1.0:
            raise InputError("err_bad_option", detail=ref("d_field_min_format", item=item))
        result[path] = number
    return result


def _emit(text: str, out: str | None, lang: str) -> None:
    """Print to stdout, or write to ``--out`` and say so."""
    if out is None:
        sys.stdout.write(text)
        return
    try:
        Path(out).write_text(text, encoding="utf-8")
    except OSError as exc:
        raise InputError("err_output_file", path=out, detail=str(exc)) from exc
    print(t(lang, "wrote", path=out))


def _cmd_score(args: argparse.Namespace, lang: str) -> int:
    if args.min_f1 is not None and not 0.0 <= args.min_f1 <= 1.0:
        raise InputError("err_bad_option", detail=ref("d_min_f1_range"))
    if args.top < 0:
        raise InputError("err_bad_option", detail=ref("d_top_negative"))
    field_min = _parse_field_min(args.field_min)
    report = evaluate_files(args.gold, args.pred, _load_config(args.config), id_key=args.id_key)
    gated = args.min_f1 is not None or bool(field_min)
    failures = check_gates(report, min_f1=args.min_f1, field_min=field_min)

    if args.format == "json":
        data = report.to_dict(args.top)
        if gated:
            data["gate"] = {
                "passed": not failures,
                "failures": [{"field": f.path, "f1": f.f1, "minimum": f.minimum} for f in failures],
            }
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    elif args.format == "md":
        text = report_markdown(report, lang, args.top, failures, gated)
    else:
        text = report_text(report, lang, args.top, failures, gated)
    _emit(text, args.out, lang)
    if args.out and gated:  # keep the verdict visible in the CI log even when the report went to a file
        for line in _gate_summary(failures, lang):
            print(line)
    return 1 if failures else 0


def _gate_summary(failures, lang: str) -> list[str]:
    lines = [t(lang, "gate_fail_line", path=f.path, f1=f"{f.f1:.3f}", minimum=f"{f.minimum:.3f}") for f in failures]
    lines.append(t(lang, "gate_fail", n=len(failures)) if failures else t(lang, "gate_pass"))
    return lines


def _cmd_diff(args: argparse.Namespace, lang: str) -> int:
    config = _load_config(args.config)
    report_a = evaluate_files(args.gold, args.pred_a, config, id_key=args.id_key)
    report_b = evaluate_files(args.gold, args.pred_b, config, id_key=args.id_key)
    result = diff_reports(report_a, report_b, tolerance=args.tolerance)
    if args.format == "json":
        text = json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n"
    elif args.format == "md":
        text = diff_markdown(result, lang)
    else:
        text = diff_text(result, lang)
    _emit(text, args.out, lang)
    return 1 if args.fail_on_regression and result.regressions else 0


def _cmd_demo(args: argparse.Namespace, lang: str) -> int:
    if args.export:
        return _export_demo(Path(args.export), lang)
    config = Config.from_file(SAMPLE_DIR / "fields.toml")
    gold = SAMPLE_DIR / "gold.jsonl"
    report_a = evaluate_files(gold, SAMPLE_DIR / "pred_a.jsonl", config)
    report_b = evaluate_files(gold, SAMPLE_DIR / "pred_b.jsonl", config)
    print(t(lang, "demo_banner"))
    print()
    print(f"=== {t(lang, 'demo_run_a')}")
    sys.stdout.write(report_text(report_a, lang))
    print()
    print(f"=== {t(lang, 'demo_run_b')}")
    sys.stdout.write(diff_text(diff_reports(report_a, report_b), lang))
    print()
    print(t(lang, "demo_next"))
    return 0


def _export_demo(target: Path, lang: str) -> int:
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise InputError("err_export_exists", path=str(target))
    shutil.copytree(SAMPLE_DIR, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    print(t(lang, "demo_banner"))
    print(t(lang, "demo_exported", path=target))
    print(f"  extractscore score {target}/gold.jsonl {target}/pred_a.jsonl --config {target}/fields.toml --min-f1 0.95")
    print(f"  extractscore diff {target}/gold.jsonl {target}/pred_a.jsonl {target}/pred_b.jsonl --config {target}/fields.toml --fail-on-regression")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
