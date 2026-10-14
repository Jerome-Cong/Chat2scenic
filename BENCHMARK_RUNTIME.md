# Public workflow benchmark runtime

This integration runs the public workflow through a query-only stdin entry point.
It is a development profile, not the paper's original model configuration and not
formal BusScene scoring. Shared scoring, runtime records and ego normalization
live in the sibling ChatScene benchmark package.

## Environments

Keep generation and simulation separate. Install generation dependencies into
`runtimes/chat2scenic/.venv` using Python 3.10 and
`requirements-benchmark.txt`. Install CPU PyTorch separately:

```bash
uv venv --python 3.10 runtimes/chat2scenic/.venv
uv pip install --python runtimes/chat2scenic/.venv/bin/python torch==2.5.1+cpu --index-url https://download.pytorch.org/whl/cpu
uv pip install --python runtimes/chat2scenic/.venv/bin/python -r requirements-benchmark.txt
uv venv --python 3.10 runtimes/scenic3/.venv
uv pip install --python runtimes/scenic3/.venv/bin/python -r requirements-scenic-runtime.txt
```

The simulation profile uses the official Scenic 3.0.0 wheel, CARLA 0.9.15,
Shapely 2.0.7, `mode2D=True` and `use2DMap=True`. Shapely 2.1 changes the private
points ABI used by Scenic 3.0.0. The official wheel already provides the trajectory
and traffic-light behavior extensions; no ChatScene extension was transplanted.

Restore the published Milvus snapshot into a new isolated standalone instance,
not over existing data. The verified local instance uses Milvus 2.6.3, embedded
etcd/local storage, `DEPLOY_MODE=STANDALONE` and loopback port 19531. The code
collection contains 922 items with 384-dimensional all-MiniLM-L6-v2 embeddings.
The public workflow's documentation retrieval calls are commented out; this
profile does not claim that both retrieval channels run.

## Query and model profile

`benchmark_query_adapter.py --model-name MODEL` reads the exact UTF-8 surface
query from stdin and writes `artifact.scenic` in a fresh working directory.
`--input-json` is only an explicit standalone diagnostic option. Successful
stdout is a single JSON disposition; native logs and state are retained under
`native/`. Code is copied from native `selected_code` without syntax or semantic
repair. The shared finalizer changes only the approved ego blueprint and size.

Use an explicit OpenAI-compatible profile through `OPENAI_API_KEY` and
`OPENAI_BASE_URL`; never put credentials in source or artifacts. The local
verified generation model is DeepSeek-V4.1-Flash for all five agents, replacing
hardcoded Gemini choices. One unconditional `confirm` follows interpretation;
there is no semantic feedback or user-directed improvement loop. The model
profile uses temperature 0.2, top_p 0.9, max_tokens 16384, timeout 180 seconds
and two API retries. A 4096-token probe exhausted its budget on reasoning with
empty content; the original failure is retained separately.

The shared preparation script freezes every embedding model file in an
`--embedding-catalog`, avoiding mutable remote model lookup during generation.
Do not edit bound source, model files or environment controls during a grid.
Use the ChatScene scripts `prepare_public_baseline_generation.py`,
`run_public_baseline_generation.py`, `prepare_public_baseline_runtime.py` and
`run_public_baseline_runtime.py` for the full development grid and record reload.
All failures stay in the declared denominator. Initial-state observations are
not simulated trajectories; formal gold, calibration and Judge gates remain.

## Verification

```bash
runtimes/chat2scenic/.venv/bin/python -m unittest discover -s tests
```

See `../ChatScene/docs/benchmark/BW10_PUBLIC_BASELINES_RUNTIME_REPORT_2026-10-14.md`
for measured local results and limitations. Local environments, credentials and
native workspaces are ignored by Git.

The complete local one-query/five-call grid produced five artifacts; three compiled
and two passed all five realization seeds and native execution. The two execution
traces completed 300/94 steps (30.0/9.4 seconds); the latter met its native stop
condition. These are engineering outcomes, not semantic accuracy. Per-artifact
owned CARLA servers prevent a shutdown crash from contaminating later records.
The recorded local shutdown exit codes remain -11; no normal-exit claim is made.
Initial diagnostics use a declared development-only profile (one CPU, 2 GiB,
20 CPU seconds, 30 wall seconds); formal extraction keeps its original budget.
