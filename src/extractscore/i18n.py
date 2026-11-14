"""Display language: English and Korean.

All user-visible text lives in ``MESSAGES`` (one table, two languages with identical
keys).  Language precedence for the CLI: ``--lang`` > ``EXTRACTSCORE_LANG`` >
``LC_ALL`` / ``LC_MESSAGES`` / ``LANG``.  Anything that does not start with ``ko``
is English.  JSON output keys never change with the language.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

LANGS = ("en", "ko")
ENV_VAR = "EXTRACTSCORE_LANG"

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # ---- table headings and report text
        "title_score": "Field-level extraction score ({n} documents)",
        "title_score_one": "Field-level extraction score ({n} document)",
        "hdr_field": "Field",
        "hdr_type": "Type",
        "hdr_precision": "Precision",
        "hdr_recall": "Recall",
        "hdr_errors": "Errors",
        "row_micro": "Micro (all fields)",
        "line_macro": "Macro F1 (mean of field F1): {value}",
        "line_skipped": "Skipped - not scored, and not counted as passing: {fields}",
        "line_parse_failures": "Parse failures or missing predictions: {n} document(s): {ids}",
        "line_extra_docs": "Predictions without a gold document (ignored): {ids}",
        "line_top_docs": "Documents with the most errors:",
        "row_top_doc": "{id}: {n} error(s)",
        "line_large_list": "Warning: {path} has {n} unmatched items; pairing is O(n^3) and may be slow.",
        "line_legend": (
            "Error categories: wrong_value = different value; type_error = value cannot be read as the field type; "
            "missing = gold has it, prediction is empty; hallucinated = prediction has it, gold does not; "
            "parse_failure = prediction line broken or absent."
        ),
        "na": "n/a",
        # ---- gate
        "gate_title": "Gate",
        "gate_fail_line": "FAIL {path}: F1 {f1} < {minimum}",
        "gate_pass": "PASS: every gated field meets its minimum F1",
        "gate_fail": "FAIL: {n} field(s) below their minimum F1",
        # ---- diff
        "title_diff": "Run comparison, A -> B ({n} documents)",
        "title_diff_one": "Run comparison, A -> B ({n} document)",
        "hdr_f1_a": "F1 A",
        "hdr_f1_b": "F1 B",
        "hdr_change": "Change",
        "hdr_status": "Status",
        "status_improved": "improved",
        "status_regressed": "REGRESSED",
        "status_same": "same",
        "line_micro_diff": "Micro F1: {a} -> {b}",
        "line_parse_diff": "Parse failures: A {a}, B {b}",
        "line_flips": "Fields that flipped in a document:",
        "line_no_flips": "No field flipped between the two runs.",
        "row_flip": "{doc}  {path}: {frm} -> {to}",
        "flip_correct": "correct",
        "flip_wrong": "wrong",
        "line_regressions": "Regressed fields ({n}): {fields}",
        "line_no_regressions": "No regressions.",
        # ---- demo and CLI output
        "demo_banner": "Practice mock: hand-written predictions that imitate typical LLM mistakes; no model is called.",
        "demo_run_a": "Run A - original prompt (hand-written predictions)",
        "demo_run_b": "Run B vs run A - prompt v2 (hand-written predictions)",
        "demo_next": "Try it on the files yourself: extractscore demo --export DIR",
        "demo_exported": "Exported the practice files to {path}. Try:",
        "wrote": "Wrote {path}",
        "error_prefix": "error",
        # ---- help
        "help_description": "Score LLM-extracted JSON against a gold set, field by field (precision, recall, F1), and compare two runs.",
        "help_score": "Score predictions against the gold JSONL and print per-field precision/recall/F1.",
        "help_diff": "Score two runs against the same gold JSONL and show what improved or regressed.",
        "help_demo": "Run the bundled practice mock (invoices and receipts, hand-written predictions).",
        "help_gold": "gold JSONL: one JSON object per line with an id plus the correct fields",
        "help_pred": "predictions JSONL, same shape as the gold file",
        "help_pred_a": "predictions JSONL of run A (before)",
        "help_pred_b": "predictions JSONL of run B (after)",
        "help_config": "field rules, TOML or JSON file (types, tolerances, fuzzy text, ignored fields)",
        "help_id_key": "key that identifies a document in both files (default: id)",
        "help_format": "output format (default: table)",
        "help_out": "write the report to this file instead of printing it",
        "help_min_f1": "exit 1 if any scored field has F1 below this value (0 to 1)",
        "help_field_min": "per-field minimum F1 as PATH=VALUE, repeatable (e.g. total=0.99)",
        "help_top": "how many most-wrong documents to list (default: 5)",
        "help_fail_regress": "exit 1 if any field regressed from A to B",
        "help_tolerance": "F1 drop allowed before a field counts as regressed (default: 0)",
        "help_export": "copy the practice files (gold, predictions, rules, source texts) to DIR",
        "help_lang": "display language: en or ko (default: EXTRACTSCORE_LANG, then LANG)",
        "help_version": "show the version and exit",
        "help_help": "show this help message and exit",
        "usage_prefix": "usage: ",
        "title_positional": "positional arguments",
        "title_options": "options",
        "title_commands": "commands",
        "ap_error": "error",
        "ap_required": "the following arguments are required: {names}",
        "ap_unrecognized": "unrecognized arguments: {names}",
        "ap_invalid_choice": "invalid choice: {value} (choose from {choices})",
        "ap_invalid_value": "invalid {kind} value: {value}",
        "ap_expected_one": "expected one argument",
        "ap_argument": "argument {name}: {message}",
        "line_errors_total": "Errors overall: {value}",
        # ---- errors
        "err_config_file": "Cannot read config file {path}: {detail}. Check the path and that it is valid TOML or JSON.",
        "err_config_unknown_key": "Unknown key {key!r} in {where}. Allowed keys: {allowed}.",
        "err_config_value": "Invalid value in {where}: {detail}.",
        "err_input_file": "Cannot read {path}: {detail}. Check that the file exists and is UTF-8 text.",
        "err_gold_line": "Gold file {path}, line {line}: {detail}. Fix or remove that line; the gold file must be valid JSON Lines with one object per line.",
        "err_missing_id": "Gold {path}, line {line}: missing the {id_key!r} key. Add it, or choose another key with --id-key.",
        "err_duplicate_id": "Duplicate document id {doc_id!r} in the gold set (line {line}). Ids must be unique.",
        "err_no_gold": "The gold set has no documents. Provide at least one JSON line.",
        "err_not_iterable": "Expected an iterable of dicts or a {id: dict} mapping.",
        "err_diff_docs": "Both runs must be scored against the same gold set, but the document ids differ.",
        "err_bad_option": "Invalid option: {detail}.",
        "err_unknown_field": "Field {path!r} is not in the report, so its minimum cannot be checked. Known fields: {known}.",
        "err_export_exists": "{path} already exists and is not empty. Choose a new or empty directory.",
        "err_output_file": "Cannot write {path}: {detail}. Check that the folder exists and is writable.",
        "d_min_f1_range": "--min-f1 must be between 0 and 1",
        "d_top_negative": "--top must be 0 or more (0 hides the list)",
        "d_field_min_format": "--field-min {item!r} must look like PATH=VALUE with VALUE between 0 and 1",
        "d_tolerance_negative": "tolerance must be >= 0",
        "d_range_0_1": "must be in (0, 1]",
        "d_date_formats_nonempty": "must be a non-empty list of strptime formats",
        "d_date_formats_list": "must be a list of strptime formats",
        "d_top_table": "top level must be a table/object",
        "d_fields_table": "must be a table/object of field rules",
        "d_field_table": "must be a table/object",
        "d_config_ext": "the file extension must be .toml or .json",
        "d_type_unknown": "{type} is not one of {allowed}",
        "d_tol_negative": "must be >= 0",
        "d_fuzzy_text_only": "fuzzy matching is only allowed on text fields, not {type} (ids and amounts stay exact)",
        "d_tol_number_only": "tol is only allowed on number fields",
        "d_expected_number": "expected a number, got {value}",
        "d_not_object": "expected an object, got {kind}",
    },
    "ko": {
        "title_score": "필드 단위 추출 점수 (문서 {n}건)",
        "title_score_one": "필드 단위 추출 점수 (문서 {n}건)",
        "hdr_field": "필드",
        "hdr_type": "형",
        "hdr_precision": "정밀도",
        "hdr_recall": "재현율",
        "hdr_errors": "오류",
        "row_micro": "마이크로 (전체 필드)",
        "line_macro": "매크로 F1 (필드별 F1 평균): {value}",
        "line_skipped": "건너뜀 - 채점하지 않았고 통과로도 세지 않음: {fields}",
        "line_parse_failures": "파싱 실패 또는 예측 없음: 문서 {n}건: {ids}",
        "line_extra_docs": "정답 문서가 없는 예측(무시함): {ids}",
        "line_top_docs": "오류가 가장 많은 문서:",
        "row_top_doc": "{id}: 오류 {n}건",
        "line_large_list": "경고: {path} 에 짝이 안 정해진 항목이 {n}개 있어 짝짓기가 O(n^3) 이라 느릴 수 있습니다.",
        "line_legend": (
            "오류 범주: wrong_value = 값이 다름; type_error = 필드 형으로 읽을 수 없음; "
            "missing = 정답에는 있는데 예측이 비어 있음; hallucinated = 예측에는 있는데 정답에 없음; "
            "parse_failure = 예측 줄이 깨졌거나 없음."
        ),
        "na": "n/a",
        "gate_title": "게이트",
        "gate_fail_line": "실패 FAIL {path}: F1 {f1} < {minimum}",
        "gate_pass": "통과 PASS: 게이트 대상 필드가 모두 최소 F1 을 넘었습니다",
        "gate_fail": "실패 FAIL: 최소 F1 에 못 미친 필드 {n}개",
        "title_diff": "실행 비교, A -> B (문서 {n}건)",
        "title_diff_one": "실행 비교, A -> B (문서 {n}건)",
        "hdr_f1_a": "F1 A",
        "hdr_f1_b": "F1 B",
        "hdr_change": "변화",
        "hdr_status": "상태",
        "status_improved": "개선",
        "status_regressed": "후퇴",
        "status_same": "동일",
        "line_micro_diff": "마이크로 F1: {a} -> {b}",
        "line_parse_diff": "파싱 실패: A {a}건, B {b}건",
        "line_flips": "문서 안에서 맞음/틀림이 바뀐 필드:",
        "line_no_flips": "두 실행 사이에 뒤집힌 필드가 없습니다.",
        "row_flip": "{doc}  {path}: {frm} -> {to}",
        "flip_correct": "맞음",
        "flip_wrong": "틀림",
        "line_regressions": "후퇴한 필드 ({n}개): {fields}",
        "line_no_regressions": "후퇴한 필드가 없습니다.",
        "demo_banner": "연습용 목: 흔한 LLM 실수를 흉내 낸 손으로 만든 예측입니다. 모델은 호출하지 않습니다.",
        "demo_run_a": "실행 A - 기존 프롬프트 (손으로 만든 예측)",
        "demo_run_b": "실행 B 대 실행 A - 프롬프트 v2 (손으로 만든 예측)",
        "demo_next": "직접 파일로 해 보려면: extractscore demo --export DIR",
        "demo_exported": "연습용 파일을 {path} 에 꺼냈습니다. 이렇게 해 보세요:",
        "wrote": "{path} 에 저장했습니다",
        "error_prefix": "오류",
        "help_description": "LLM 으로 뽑은 JSON 을 정답 세트와 필드 단위(정밀도·재현율·F1)로 채점하고, 두 실행을 비교합니다.",
        "help_score": "예측을 정답 JSONL 과 비교해 필드별 정밀도·재현율·F1 을 출력합니다.",
        "help_diff": "같은 정답으로 두 실행을 채점해 무엇이 좋아지고 나빠졌는지 보여 줍니다.",
        "help_demo": "동봉된 연습용 목(송장·영수증, 손으로 만든 예측)을 실행합니다.",
        "help_gold": "정답 JSONL: 한 줄에 id 와 정답 필드가 든 JSON 객체 하나",
        "help_pred": "예측 JSONL (정답 파일과 같은 모양)",
        "help_pred_a": "실행 A(이전)의 예측 JSONL",
        "help_pred_b": "실행 B(이후)의 예측 JSONL",
        "help_config": "필드 규칙 TOML 또는 JSON 파일 (형, 허용 오차, 퍼지 텍스트, 제외 필드)",
        "help_id_key": "두 파일에서 문서를 구분하는 키 (기본: id)",
        "help_format": "출력 형식 (기본: table)",
        "help_out": "화면에 출력하지 않고 이 파일에 보고서를 씁니다",
        "help_min_f1": "채점된 필드 중 F1 이 이 값(0~1)보다 낮은 것이 있으면 종료 코드 1",
        "help_field_min": "필드별 최소 F1 을 PATH=값 으로 지정, 여러 번 가능 (예: total=0.99)",
        "help_top": "오류가 많은 문서를 몇 건 보여 줄지 (기본: 5)",
        "help_fail_regress": "A 에서 B 로 후퇴한 필드가 있으면 종료 코드 1",
        "help_tolerance": "후퇴로 세기 전에 허용하는 F1 하락 폭 (기본: 0)",
        "help_export": "연습용 파일(정답·예측·규칙·원문)을 DIR 로 복사합니다",
        "help_lang": "표시 언어: en 또는 ko (기본: EXTRACTSCORE_LANG, 그다음 LANG)",
        "help_version": "버전을 보여 주고 끝냅니다",
        "help_help": "이 도움말을 보여 주고 끝냅니다",
        "usage_prefix": "사용법: ",
        "title_positional": "위치 인자",
        "title_options": "옵션",
        "title_commands": "명령",
        "ap_error": "오류",
        "ap_required": "다음 인자가 필요합니다: {names}",
        "ap_unrecognized": "알 수 없는 인자: {names}",
        "ap_invalid_choice": "잘못된 선택: {value} ({choices} 중에서 고르세요)",
        "ap_invalid_value": "{kind} 값이 올바르지 않습니다: {value}",
        "ap_expected_one": "값이 하나 필요합니다",
        "ap_argument": "인자 {name}: {message}",
        "line_errors_total": "전체 오류: {value}",
        "err_config_file": "설정 파일 {path} 을(를) 읽을 수 없습니다: {detail}. 경로와 TOML/JSON 문법을 확인하세요.",
        "err_config_unknown_key": "{where} 에 알 수 없는 키 {key!r} 가 있습니다. 쓸 수 있는 키: {allowed}.",
        "err_config_value": "{where} 의 값이 올바르지 않습니다: {detail}.",
        "err_input_file": "{path} 을(를) 읽을 수 없습니다: {detail}. 파일이 있고 UTF-8 텍스트인지 확인하세요.",
        "err_gold_line": "정답 파일 {path} {line}번째 줄: {detail}. 그 줄을 고치거나 지우세요. 정답 파일은 한 줄에 객체 하나인 올바른 JSON Lines 여야 합니다.",
        "err_missing_id": "정답 {path} {line}번째 줄에 {id_key!r} 키가 없습니다. 키를 추가하거나 --id-key 로 다른 키를 고르세요.",
        "err_duplicate_id": "정답 세트에 문서 id {doc_id!r} 가 중복됩니다 ({line}번째 줄). id 는 유일해야 합니다.",
        "err_no_gold": "정답 세트에 문서가 없습니다. JSON 줄을 하나 이상 넣으세요.",
        "err_not_iterable": "dict 의 반복 가능 객체이거나 {id: dict} 매핑이어야 합니다.",
        "err_diff_docs": "두 실행은 같은 정답 세트로 채점해야 하는데 문서 id 가 다릅니다.",
        "err_bad_option": "옵션이 올바르지 않습니다: {detail}.",
        "err_unknown_field": "필드 {path!r} 가 보고서에 없어 최소값을 확인할 수 없습니다. 있는 필드: {known}.",
        "err_export_exists": "{path} 가 이미 있고 비어 있지 않습니다. 새 디렉터리나 빈 디렉터리를 고르세요.",
        "err_output_file": "{path} 에 쓸 수 없습니다: {detail}. 폴더가 있고 쓸 수 있는지 확인하세요.",
        "d_min_f1_range": "--min-f1 은 0 이상 1 이하여야 합니다",
        "d_top_negative": "--top 은 0 이상이어야 합니다 (0 이면 목록을 숨깁니다)",
        "d_field_min_format": "--field-min {item!r} 은 PATH=값 형태여야 하고 값은 0 이상 1 이하여야 합니다",
        "d_tolerance_negative": "허용 오차(tolerance)는 0 이상이어야 합니다",
        "d_range_0_1": "0 초과 1 이하여야 합니다",
        "d_date_formats_nonempty": "strptime 형식의 비어 있지 않은 목록이어야 합니다",
        "d_date_formats_list": "strptime 형식의 목록이어야 합니다",
        "d_top_table": "최상위는 테이블/객체여야 합니다",
        "d_fields_table": "필드 규칙의 테이블/객체여야 합니다",
        "d_field_table": "테이블/객체여야 합니다",
        "d_config_ext": "파일 확장자는 .toml 또는 .json 이어야 합니다",
        "d_type_unknown": "{type} 는 {allowed} 중 하나가 아닙니다",
        "d_tol_negative": "0 이상이어야 합니다",
        "d_fuzzy_text_only": "퍼지 매칭은 텍스트 필드에만 쓸 수 있고 {type} 에는 쓸 수 없습니다 (id·금액은 정확히 비교)",
        "d_tol_number_only": "tol 은 숫자 필드에만 쓸 수 있습니다",
        "d_expected_number": "숫자가 필요한데 {value} 를 받았습니다",
        "d_not_object": "객체가 필요한데 {kind} 를 받았습니다",
    },
}


def resolve_lang(cli_lang: str | None = None, environ: Mapping[str, str] | None = None) -> str:
    """Pick ``"en"`` or ``"ko"``: ``--lang`` > ``EXTRACTSCORE_LANG`` > ``LC_ALL`` > ``LC_MESSAGES`` > ``LANG``."""
    env = os.environ if environ is None else environ
    for candidate in (cli_lang, env.get(ENV_VAR), env.get("LC_ALL"), env.get("LC_MESSAGES"), env.get("LANG")):
        if candidate:
            return "ko" if candidate.strip().lower().startswith("ko") else "en"
    return "en"


class Ref:
    """A message key used as a parameter of another message (e.g. an error detail).

    ``str(ref)`` is the English text, so ``str(exc)`` stays English; the CLI asks
    :meth:`localized` for the user's language.
    """

    def __init__(self, key: str, params: Mapping[str, object]) -> None:
        self.key = key
        self.params = dict(params)

    def localized(self, lang: str) -> str:
        return t(lang, self.key, **self.params)

    def __str__(self) -> str:
        return self.localized("en")


def ref(key: str, /, **params: object) -> Ref:
    """Build a :class:`Ref` to message ``key`` with ``params``."""
    return Ref(key, params)


def t(lang: str, key: str, /, **params: object) -> str:
    """Look up ``key`` in ``lang`` (unknown languages fall back to English) and format it."""
    table = MESSAGES.get(lang, MESSAGES["en"])
    return table[key].format(**params) if params else table[key]


def title_score(lang: str, n: int) -> str:
    """Score title with the document count (singular form when ``n == 1``)."""
    return t(lang, "title_score_one" if n == 1 else "title_score", n=n)


def title_diff(lang: str, n: int) -> str:
    """Diff title with the document count (singular form when ``n == 1``)."""
    return t(lang, "title_diff_one" if n == 1 else "title_diff", n=n)
