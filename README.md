# DatasetBrief

Understand a CSV before starting an analysis. DatasetBrief generates a local HTML report with missingness, column statistics and quality findings. An optional Ollama model explains what the dataset might describe and suggests checks grounded in those statistics.

## Try it

Requires Python 3.11 or newer. Clone this repository, open its directory, then run:

```sh
python -m pip install .
datasetbrief examples/subscriptions.csv --output datasetbrief-report
```

Open `datasetbrief-report/report.html` in a browser. The same directory contains `profile.json` for programmatic use. You can also run `python -m datasetbrief` with the same arguments.

A generated [example HTML report](docs/example-report/report.html) and its [JSON profile](docs/example-report/profile.json) are included in this repository. Download the HTML file and open it locally.

The included subscription dataset is synthetic. It deliberately contains missing fields, one duplicated row, a constant column and an unusually large spend value.

## Add an AI explanation

Install [Ollama](https://ollama.com), start it and download a model suited to your hardware:

```sh
ollama pull llama3.2:3b
datasetbrief examples/subscriptions.csv --ai-model llama3.2:3b --output local-report-ai
```

AI receives column names, aggregate counts and numeric summaries. It receives no raw rows, example values, category labels, source paths or filenames. Column names and numeric summaries can still contain sensitive information. The default endpoint is local. If you set `--ai-endpoint`, those aggregates go to the endpoint you choose.

AI interpretations are labeled as generated content. The prompt asks the model to distinguish measured facts from hypotheses, avoid inventing units or provenance, and acknowledge that missingness mechanisms cannot be determined from a profile alone. Counts and statistics are computed in Python.

When AI is unavailable or returns an invalid response, the HTML and JSON profile are still saved and the command exits with code 2. Exit code 0 means success, and code 1 indicates a profiling or output error. Argument errors also use code 2.

## What the report includes

- Dataset shape, missing-cell percentage, incomplete-row count and duplicate-row count.
- Missing values by column and the ten most frequent combinations of missing fields.
- Numeric, boolean and text types, distinct-value counts, and numeric min/median/max.
- Constant columns, all-missing columns, infinite values and possible identifier columns.
- Descriptive 1.5×IQR outlier counts when the interquartile range is nonzero.
- Optional AI summary, possible row meaning, caveats and suggested next steps.

## Use your own data

```sh
datasetbrief data.csv --output local-report-custom
datasetbrief data.csv --na UNKNOWN --na -999 --max-rows 50000 --output local-report-prefix
datasetbrief data.tsv --delimiter "\t" --encoding utf-8 --output local-report-tsv
```

Pandas default NA markers, empty fields and whitespace-only fields count as missing. Additional markers are opt-in. For example, use `--na UNKNOWN` only when UNKNOWN means absent in your dataset. Fully blank rows are retained.

The default run reads the full CSV into memory. Use `--max-rows` for a bounded prefix scan on large files. Every report states whether it covers all rows or just the first N rows. A prefix can be biased if the file is ordered.

Types follow pandas inference. Dates and mixed-type columns may appear as text. A unique column is only an identifier candidate. IQR flags do not establish that values are erroneous. No automatic cleaning or imputation is performed. Reports contain column names and numeric summaries, so review them before sharing.

Use a new output directory for each run. Existing directories are rejected to preserve earlier reports.

## Python

```python
from datasetbrief import profile_csv

profile = profile_csv("data.csv", max_rows=50000)
print(profile["missing_pct"])
print(profile["findings"])
```

## Development

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

The tests cover missingness and duplicate counts, scan boundaries, safe HTML rendering, strict JSON serialization and the AI request/response contract. AI tests use a mock endpoint response, so they require no model download.

Contributions are welcome through issues and pull requests. Include a minimal synthetic CSV when reporting a parsing issue, along with the command and Python/pandas versions.

MIT licensed. AI integration follows the [Ollama chat API](https://docs.ollama.com/api/chat), and CSV parsing follows [pandas.read_csv](https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html).
