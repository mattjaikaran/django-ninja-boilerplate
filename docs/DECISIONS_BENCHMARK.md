# Decision provider benchmark

This page describes the decision eval harness, the bundled benchmark, and the
results for Laya and CLM. It also explains why Laya stays the default
provider. Read the [caveats](#caveats) before you use any number here.

## Summary

- Laya stays the default provider. On the held-out test split it scored 65.8%
  overall against 62.0% for CLM, and it was better on four of the five choice
  questions. It needs no encoder service, and a warm decision took 111 ms at
  the median.
- CLM was better on four of the eight yes/no (`noul`) questions, with large
  margins on `needs_migration_review` (97.7% against 48.8%) and
  `security_sensitive` (95.3% against 60.5%). Its choice answers collapsed
  toward one label.
- Neither provider is fit to route agent tasks by model tier, or to decide
  alone whether an action is destructive or needs approval. Both scored at or
  below the majority-class rate on `tier`, `destructive`, and
  `needs_approval`.
- Jev was not measured. No `TYPESAFE_API_KEY` was available; the harness
  recorded Jev as skipped.

## The harness

| Command | Recipe | Purpose |
|---|---|---|
| `eval_decisions` | `just eval-decisions`, `just decisions-benchmark <provider>` | Run labelled cases through one provider and write a JSON report |
| `compare_decisions` | `just decisions-compare` | Compare saved reports on the held-out `test` split |
| `recommend_thresholds` | `just decisions-thresholds <report>` | Tune per-question thresholds on `dev`, check them on `test`, and write `DECISION_THRESHOLDS_FILE` |

A report holds, overall, per dataset, and per question:

- accuracy and mean confidence;
- expected calibration error (ECE) and reliability bins (ten equal-width
  confidence bins);
- coverage and accuracy at each threshold from 0.5 to 0.95;
- latency: the first (cold) call, and the warm p50 and p95;
- cost per call and total cost, when `DECISION_PROVIDER_COSTS` sets a price;
- every scored answer, with its case id and split;
- the host, Python version, and package versions.

The harness evaluates exactly the provider you name. When that provider is
unavailable, the command fails. With `--skip-unavailable`, it writes a
`skipped` report with the reason. It never runs another provider in its
place. `compare_decisions` lists skipped providers with their reason.

### Use your own traffic

Export reviewed decisions as JSONL, one case per line:

```json
{"id": "t-1041", "split": "test", "state": {"ticket": "..."}, "expected": {"team": "billing"}}
```

Put the shared question definitions in a `questions.json` next to the file,
or pass `--questions`. A line can also carry its own `questions`. Only
`choice` and `noul` questions can be scored; the loader rejects any other
type before it calls a provider.

```bash
python manage.py eval_decisions reviewed.jsonl --questions questions.json \
  --provider laya --output reports/decisions/laya.json
python manage.py recommend_thresholds reports/decisions/laya.json --target 0.95
```

Give each case a `dev` or `test` split before you look at any result. Tune
wording and thresholds on `dev` only.

## The benchmark

`decisions/data/benchmark/` holds five domains. Each domain has a
`questions.json` and a `cases.jsonl`. The agent tools in
[Decisions for agents](DECISIONS_FOR_AGENTS.md) use these same question
definitions.

| Domain | Cases | Dev | Test | Hard | Questions |
|---|---|---|---|---|---|
| `support_triage` | 65 | 20 | 45 | 17 | `team` (3-way), `urgent`, `wants_refund`, `angry` |
| `code_review_triage` | 65 | 22 | 43 | 17 | `change_type` (5-way), `needs_migration_review`, `security_sensitive` |
| `task_routing` | 65 | 24 | 41 | 16 | `tier` (local, mid, frontier), `needs_human` |
| `risk_flags` | 65 | 23 | 42 | 19 | `destructive`, `needs_approval`, `scope` (3-way) |
| `generator_choice` | 50 | 20 | 30 | 13 | `generator` (10-way) |
| Total | 310 | 109 | 201 | 82 | 830 labels |

How the benchmark was built:

1. The question wording was written first and was not changed after any
   provider result.
2. One annotator wrote each domain's cases and labels from the criteria text.
3. A second annotator labelled the same cases blind, from the state and the
   criteria only.
4. A third annotator settled each disagreement from the criteria text. The
   adjudicator kept the first label 17 times and the second label 28 times.
5. A hash of each case id assigned the split: about 40% `dev`, 60% `test`.

All three annotators were LLM agents, not people. Agreement between the two
blind annotators, before adjudication:

| Question | Agreement | Cohen's kappa |
|---|---|---|
| `team` | 98.5% | 0.98 |
| `urgent` | 95.4% | 0.89 |
| `wants_refund` | 100% | 1.00 |
| `angry` | 83.1% | 0.53 |
| `change_type` | 92.3% | 0.90 |
| `needs_migration_review` | 100% | 1.00 |
| `security_sensitive` | 95.4% | 0.89 |
| `tier` | 84.6% | 0.76 |
| `needs_human` | 90.8% | 0.78 |
| `destructive` | 95.4% | 0.89 |
| `needs_approval` | 98.5% | 0.97 |
| `scope` | 98.5% | 0.98 |
| `generator` | 98.0% | 0.98 |

`angry` and `tier` have the most label noise. Treat their scores with the
least trust.

## Results

Host: Apple M2 Pro, 32 GB, macOS 15.7.4 (arm64), Python 3.13.5, Django
5.2.17. Recorded on 2026-09-29.

- Laya: `laya` 0.3.11, `torch` 2.14.0, `transformers` 4.57.6, in-process on
  the host. Laya warned: "this checkpoint ships invalid temperatures ... using
  choice:11+ ... Treat confidence from the affected entries as uncalibrated."
  No question here has 11 or more options.
- CLM: the slim `clm-api` image (`python:3.12-slim`, 915 MB, arm64,
  `contrastive-lm` 0.1.0, CPU `torch` 2.14.0) in Compose with the
  `decisions-clm-host` profile. The Qwen3-8B Q8_0 encoder ran on the host with
  llama.cpp 0.5.0 (build 11146), Metal, `-c 2048 --parallel 1`. All 310 CLM
  decisions went through `POST /v1/systemone` on that image.
- The full reports are in `docs/decisions/reports/` (`laya.json`,
  `clm.json`, and the skipped `jev.json`).

Test split, 201 cases, 547 answers. "Majority" is the share of the most
common label in the test split: a provider below it does worse than always
giving that label.

| Question | n | Majority | Laya | CLM |
|---|---|---|---|---|
| `team` | 45 | 40.0% | **73.3%** | 28.9% |
| `urgent` | 45 | 77.8% | **84.4%** | 77.8% |
| `wants_refund` | 45 | 62.2% | 75.6% | **88.9%** |
| `angry` | 45 | 77.8% | **86.7%** | 80.0% |
| `change_type` | 43 | 27.9% | **81.4%** | 53.5% |
| `needs_migration_review` | 43 | 72.1% | 48.8% | **97.7%** |
| `security_sensitive` | 43 | 60.5% | 60.5% | **95.3%** |
| `tier` | 41 | 39.0% | 34.1% | 39.0% |
| `needs_human` | 41 | 65.9% | 46.3% | **73.2%** |
| `destructive` | 42 | 73.8% | 45.2% | 28.6% |
| `needs_approval` | 42 | 54.8% | 50.0% | 50.0% |
| `scope` | 42 | 52.4% | **85.7%** | 42.9% |
| `generator` | 30 | 13.3% | **83.3%** | 40.0% |
| Overall | 547 | | 65.8% | 62.0% |

| Provider | Mean confidence | ECE | Coverage at 0.8 | Accuracy at 0.8 | Cold | Warm p50 | Warm p95 |
|---|---|---|---|---|---|---|---|
| Laya | 60.8% | 0.146 | 25.6% | 70.0% | 13.4 s | 111 ms | 173 ms |
| CLM | 79.5% | 0.177 | 60.3% | 76.4% | 2.0 s | 504 ms | 605 ms |

Latency covers the whole `DecisionService.decide` call. Laya's cold call
includes loading the checkpoint. CLM's includes the HTTP call to `clm-api`
and the encoder call. The host was under memory pressure during the CLM run
(about 9.4 GB of swap in use), which can inflate CLM latency. No cost was
configured: both providers ran locally.

### What the results show

- **Confidence is not a probability for either provider.** Laya reports a
  margin for choice questions, so its confidence is low when it is right
  (`change_type`: 81.4% accurate at 26.8% mean confidence). CLM is
  overconfident on `destructive` and `needs_approval` (above 88% mean
  confidence at 50% accuracy or less).
- **Some `noul` scores rank well but cut at the wrong point.** Over all
  splits, Laya's yes probability for `needs_migration_review` ranked a true
  case above a false one 93% of the time (ROC AUC 0.93), but its accuracy at
  the 0.5 cut was 49%. CLM had AUC 0.92 on `destructive` and 28.6% accuracy.
  A per-question threshold on the confidence cannot fix a wrong cut point.
- **CLM's choice answers collapse.** CLM answered `account` for 63 of 65
  `team` cases, and `subscription` for 25 of 50 `generator` cases. CLM is
  very sensitive to criteria wording. On the older 40-ticket set, a `team`
  question with other options and wording scored 77.5%.
- **Laya's `needs_human` score points the wrong way** (AUC 0.37 over all
  splits).

### Per-question thresholds

`recommend_thresholds --target 0.9 --min-support 10` tuned a threshold per
question on `dev` and checked it on `test`. The result is in
`decisions/data/thresholds.example.json`. A question with no threshold that
reached 90% on `dev` gets 1.0, so every answer to it escalates.

| Question | Laya threshold | Laya test coverage, accuracy | CLM threshold | CLM test coverage, accuracy |
|---|---|---|---|---|
| `team` | 0.20 | 66.7%, 90.0% | 1.0 | 0% |
| `wants_refund` | 0.80 | 44.4%, 90.0% | 0.70 | 84.4%, 92.1% |
| `angry` | 0.60 | 71.1%, 93.8% | 0.70 | 62.2%, 89.3% |
| `scope` | 0.25 | 83.3%, 94.3% | 1.0 | 0% |
| `generator` | 0.90 | 56.7%, 76.5% | 1.0 | 0% |
| `change_type` | 0.10 | 90.7%, 79.5% | 1.0 | 0% |
| `needs_migration_review` | 1.0 | 0% | 0.00 | 100%, 97.7% |
| `security_sensitive` | 1.0 | 0% | 0.00 | 100%, 95.3% |
| `urgent`, `tier`, `needs_human`, `destructive`, `needs_approval` | 1.0 | 0% | 1.0 | 0% |

Dev has only 20 to 24 answers per question, so these thresholds are noisy.
`generator` and `change_type` met 90% on `dev` and missed it on `test`
(76.5% and 79.5%). Re-tune on your own reviewed traffic.

## Default provider decision

Keep `SYSTEMONE_PROVIDER=laya` as the default:

1. Laya had the higher overall test accuracy (65.8% against 62.0%).
2. Laya was better on four of the five choice questions, which drive routing
   and generator selection. CLM's choice answers collapsed toward one label.
3. Laya runs in-process with no extra service. CLM needs an 8B encoder that
   holds 8 to 9 GB of memory, or a GPU host.
4. Laya's warm latency was lower (111 ms against 504 ms p50). Its cold start
   was higher (13.4 s), so preload it in production
   (`LayaProvider(preload=True)`).

Consider CLM when your questions are mostly yes/no reviews, such as
migration or security review flags, and you can run the encoder. The server
uses one provider for every question; mixing providers per question is not
supported.

## Caveats

- The benchmark is synthetic. LLM agents wrote and labelled every case. It
  measures how providers handle realistic text, not your traffic.
- Sample sizes are small. A test question has 30 to 45 answers. At n = 45 and
  75% accuracy, a 95% confidence interval is about plus or minus 13 points,
  so differences under about 15 points are not reliable.
- Labels are noisy on `angry` (kappa 0.53) and `tier` (kappa 0.76).
- One run per provider, on one host, with no repeat. CLM ran on llama.cpp
  Q8_0, not on vLLM bf16, which its projection head was trained on. The
  llama.cpp pipeline matched a `transformers` reference at 0.6B size (cosine
  0.998 to 0.9997 on 15 of 16 texts), so it probably does not explain most of
  CLM's gap. The 8B quantization gap and vLLM parity are not measured; a vLLM
  run on a GPU would settle it.
- Jev was not measured.
- The question wording is one wording. CLM results change a lot with
  wording. Wording was not tuned for either provider.
