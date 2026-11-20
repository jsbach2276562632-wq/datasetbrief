import argparse
import json
from pathlib import Path
import sys

from .ai import explain
from .profile import profile_csv
from .report import render_html


def positive(value):
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("Must be a positive integer.")
    return parsed


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Understand a CSV with a local HTML report and optional AI interpretation."
    )
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("datasetbrief-report"))
    parser.add_argument("--delimiter", default=",", help="Use '\\t' for TSV.")
    parser.add_argument("--encoding", default="utf-8-sig")
    parser.add_argument("--na", action="append", default=[], help="Additional missing token. Repeatable.")
    parser.add_argument("--max-rows", type=positive, help="Profile the first N rows instead of the whole file.")
    parser.add_argument("--ai-model", help="Optional installed Ollama model name.")
    parser.add_argument("--ai-endpoint", default="http://localhost:11434")
    parser.add_argument("--ai-timeout", type=positive, default=120)
    args = parser.parse_args(argv)
    # A new directory keeps a prior report from being overwritten by accident.
    if args.output.exists():
        parser.error(f"Output already exists: {args.output}. Choose a new --output directory.")
    try:
        profile = profile_csv(
            args.csv, delimiter="\t" if args.delimiter == "\\t" else args.delimiter,
            encoding=args.encoding, na_values=args.na, max_rows=args.max_rows,
        )
    except (ValueError, OSError, UnicodeError) as error:
        print(f"Could not profile CSV: {error}", file=sys.stderr)
        return 1
    ai_failed = False
    if args.ai_model:
        print("Sending column names and aggregate statistics to the configured AI endpoint.", file=sys.stderr)
        try:
            profile["ai"] = explain(profile, model=args.ai_model, endpoint=args.ai_endpoint,
                                    timeout=args.ai_timeout)
        except (OSError, ValueError, KeyError, TypeError) as error:
            ai_failed = True
            profile["ai"] = {"status": "failed", "model": args.ai_model}
            print(f"AI unavailable ({type(error).__name__}); saving the computed profile.", file=sys.stderr)
    try:
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "profile.json").write_text(
            json.dumps(profile, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8"
        )
        (args.output / "report.html").write_text(render_html(profile), encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"Could not save report: {error}", file=sys.stderr)
        return 1
    print(f"{profile['rows']:,} rows | {profile['columns_count']} columns | "
          f"{profile['missing_pct']}% missing cells | {profile['duplicate_rows']} duplicate rows")
    print(f"HTML: {(args.output / 'report.html').resolve()}")
    print(f"JSON: {(args.output / 'profile.json').resolve()}")
    return 2 if ai_failed else 0
