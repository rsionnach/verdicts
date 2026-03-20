# Contributing to Verdict

## Development

### Python Library

```bash
cd lib/python
pip install -e .
python -m pytest tests/
```

### Running Evaluation Datasets

```bash
nthlayer-learn eval --producer arbiter --dataset eval/code-review/
```

## Schema Changes

The verdict schema is defined in `schema/verdict.json`. All language implementations must conform to it. When proposing schema changes:

1. Update `schema/verdict.json`
2. Update `schema/verdict.yaml` (annotated example)
3. Update all language implementations
4. Bump the `version` field

## Adding Evaluation Cases

Place evaluation verdicts in the appropriate `eval/` subdirectory. Each file should be a complete verdict with a known outcome (status is not `pending`). Include realistic reasoning and ground truth signals.
