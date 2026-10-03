# PaperDelta review

    PaperDelta — consistency with supplied experiment results
    6 confirmed bindings: 1 pass, 5 mismatch, 0 unknown
    0 unbound numeric candidates; 0 unsupported regions
    0 unregistered or unresolved figure references
    ERROR paper/abstract.tex:2 [VALUE_MISMATCH] '84.1\\%' should display '80.9\\%' from metric ours
    ERROR paper/results.tex:8 [VALUE_MISMATCH] '84.1' should display '80.9' from metric ours
    ERROR paper/results.tex:16 [VALUE_MISMATCH] '3.1' should display '-0.1' from metric gain
    ERROR paper/appendix.tex:4 [VALUE_MISMATCH] '84.1' should display '80.9' from metric ours
    ERROR paper/results.tex:17 [CLAIM_FALSE] The confirmed comparison no longer holds for the selected evidence
    2 metric changes since submitted-v1
    Review main_comparison: unreviewed (current comparison: mismatch)

## Metric changes

    {
      "after": "0.809",
      "before": "0.841",
      "claims": [
        "main_comparison"
      ],
      "kind": "changed",
      "metric": "ours",
      "occurrences": [
        "abstract_accuracy",
        "table_accuracy",
        "appendix_accuracy"
      ],
      "unit": "fraction"
    }

    {
      "after": "-0.100",
      "before": "3.100",
      "claims": [],
      "kind": "changed",
      "metric": "gain",
      "occurrences": [
        "gain_text"
      ],
      "unit": "percentage_point"
    }


## Impact groups

    {
      "change": "changed",
      "claims": [
        "main_comparison"
      ],
      "figures": [],
      "metric": "ours",
      "metrics": [
        "ours",
        "gain"
      ],
      "occurrences": [
        "abstract_accuracy",
        "table_accuracy",
        "gain_text",
        "appendix_accuracy"
      ],
      "sources": [
        "results/metrics.csv"
      ]
    }

    {
      "change": "unchanged",
      "claims": [
        "main_comparison"
      ],
      "figures": [],
      "metric": "baseline",
      "metrics": [
        "baseline",
        "gain"
      ],
      "occurrences": [
        "table_baseline",
        "gain_text"
      ],
      "sources": [
        "results/metrics.csv"
      ]
    }


This report checks declared bindings, not the scientific truth of the paper.
