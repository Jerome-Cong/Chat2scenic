"""Query-only capture of the public Chat2scenic workflow, without code repair."""

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import sys


class RedactedStream:
    def __init__(self, stream):
        self.stream = stream

    def write(self, text):
        return self.stream.write(redact(text))

    def __getattr__(self, name):
        return getattr(self.stream, name)


def read_query(stream, json_input=False):
    raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("query input exceeds its declared bound")
    if not json_input:
        query = raw.decode("utf-8")
        if not query.strip():
            raise ValueError("one non-empty surface query is required")
        return query
    request = json.loads(raw)
    if not isinstance(request, dict) or set(request) != {"query_text"}:
        raise ValueError("method input must contain only query_text")
    query = request["query_text"]
    if not isinstance(query, str) or not query.strip():
        raise ValueError("one non-empty query_text is required")
    if len(query.encode("utf-8")) > 65536:
        raise ValueError("query exceeds the declared input bound")
    return query


def redact(value):
    if isinstance(value, str):
        for name in ("OPENAI_API_KEY", "GOOGLE_API_KEY", "DEEPSEEK_API_KEY", "QWEN_API_KEY", "MILVUS_TOKEN"):
            secret = os.environ.get(name)
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    return value


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(redact(value), stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def state_snapshot(state):
    result = dict(state)
    result["messages"] = [
        {"type": message.type, "content": message.content}
        for message in state.get("messages", [])
    ]
    return result


def generate(query, args, *, workdir=None):
    root = Path(workdir or Path.cwd()).resolve()
    native = root / "native"
    native.mkdir(exist_ok=False)
    write_json(native / "request.json", {"query_text": query})
    write_json(native / "declared-profile.json", {
        "scope": "public-workflow-compatible-model", "model": args.model_name,
        "provider": "openai", "temperature": args.temperature,
        "max_tokens": args.max_tokens, "api_timeout_seconds": args.api_timeout,
        "api_max_retries": args.api_max_retries, "embedding_model": args.embedding_model,
        "embedding_device": "cpu", "milvus_uri": args.milvus_uri,
        "interaction_policy": "one unconditional mechanical confirm after interpretation",
        "post_output_semantic_repair": False,
    })
    if args.embedding_catalog:
        catalog = json.loads(args.embedding_catalog.read_text())
        directory = Path(catalog["directory"]).resolve()
        listed = set()
        for item in catalog["files"]:
            path = Path(item["path"])
            if path.is_symlink() or not path.is_file() or directory not in path.resolve().parents:
                raise ValueError("embedding catalog file escapes its model directory")
            data = path.read_bytes()
            if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError("embedding catalog file changed")
            listed.add(path.resolve())
        if listed != {p.resolve() for p in directory.rglob("*") if p.is_file()}:
            raise ValueError("embedding model directory differs from its declared catalog")
        args.embedding_model = str(directory)
    # These variables are local runtime settings, never additional query fields.
    os.environ.update(
        LLM_PROFILE_OVERRIDE="true",
        LLM_PROVIDER="openai",
        LLM_MODEL_NAME=args.model_name,
        LLM_TEMPERATURE=str(args.temperature),
        LLM_MAX_TOKENS=str(args.max_tokens),
        LLM_TIMEOUT_SECONDS=str(args.api_timeout),
        LLM_MAX_RETRIES=str(args.api_max_retries),
        MILVUS_URI=args.milvus_uri,
        EMBEDDING_PROVIDER="huggingface",
        EMBEDDING_MODEL=args.embedding_model,
        DEVICE="cpu",
        CUDA_VISIBLE_DEVICES="",
        TOKENIZERS_PARALLELISM="false",
    )
    if args.embedding_cache:
        os.environ["HF_HOME"] = str(args.embedding_cache.resolve())

    from core.workflow import SearchWorkflow
    from core.config import get_settings
    from utils import AgentLogger as logger_module
    from utils.AgentLogger import reset_agent_logger

    class SafeLogger(logger_module.AgentLogger):
        def log_agent_interaction(self, *positional, **named):
            return super().log_agent_interaction(*redact(positional), **redact(named))

        def log_workflow_event(self, *positional, **named):
            return super().log_workflow_event(*redact(positional), **redact(named))

    settings = get_settings()
    # Fail instead of silently inheriting another imported settings instance.
    if (
        not settings.LLM_PROFILE_OVERRIDE
        or settings.LLM_MODEL_NAME != args.model_name
        or settings.LLM_PROVIDER != "openai"
        or settings.MILVUS_URI != args.milvus_uri
        or settings.DEVICE != "cpu"
    ):
        raise RuntimeError("cached settings differ from the declared local profile")

    logger_module._global_agent_logger = SafeLogger(generation_id="native", user_query=redact(query))
    workflow = None
    searches = []
    model_calls = []
    try:
        workflow = SearchWorkflow(thread_id="query-only")
        client = workflow.generator_agent.scenario_client
        if client is None:
            raise RuntimeError("native scenario retrieval client is unavailable")
        if client.collection.num_entities <= 0:
            raise RuntimeError("native scenario retrieval collection is empty")

        original_search = client.search_components_by_type

        def audited_search(query, component_type, limit=5):
            record = {"query": query, "component_type": component_type, "limit": limit}
            searches.append(record)
            try:
                hits = original_search(query, component_type, limit)
                record["hits"] = [
                    {"scenario_id": hit.entity.get("scenario_id"), "score": float(hit.score)}
                    for hit in hits
                ]
                record["ok"] = True
                return hits
            except Exception as exc:
                record.update(ok=False, error_type=type(exc).__name__)
                raise

        client.search_components_by_type = audited_search
        agents = {
            name: {"model": agent.model_name, "provider": agent.model_provider}
            for name, agent in (
                ("interpretation", workflow.interpretor),
                ("components", workflow.generator_agent),
                ("header", workflow.header_generator),
                ("settings", workflow.settings_detector),
                ("query_type", workflow.regulation_query_agent),
            )
        }
        class CapturingModel:
            def __init__(self, delegate, role):
                self.delegate = delegate
                self.role = role

            def invoke(self, *positional, **named):
                response = self.delegate.invoke(*positional, **named)
                metadata = response.response_metadata or {}
                model_calls.append({
                    "role": self.role,
                    "finish_reason": metadata.get("finish_reason"),
                    "usage": response.usage_metadata,
                    "response_characters": len(response.content) if isinstance(response.content, str) else None,
                })
                return response

        for role, agent in (("interpretation", workflow.interpretor), ("components", workflow.generator_agent),
                            ("header", workflow.header_generator), ("settings", workflow.settings_detector),
                            ("query_type", workflow.regulation_query_agent)):
            agent.llm = CapturingModel(agent.llm, role)
        write_json(native / "profile.json", {
            "scope": "public-workflow-compatible-model",
            "agents": agents,
            "temperature": settings.LLM_TEMPERATURE,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "top_p": settings.LLM_TOP_P,
            "api_timeout_seconds": settings.LLM_TIMEOUT_SECONDS,
            "api_max_retries": settings.LLM_MAX_RETRIES,
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_device": settings.DEVICE,
            "collection": client.collection_name,
            "interaction_policy": "one unconditional mechanical confirm after interpretation",
            "post_output_semantic_repair": False,
        })
        state = workflow.run(user_input=query, auto_correction=False)
        write_json(native / "before-confirmation.json", state_snapshot(state))
        if state.get("workflow_status") == "awaiting_confirmation":
            state = workflow.run(user_feedback="confirm", auto_correction=False)
        write_json(native / "final-state.json", state_snapshot(state))
        # The upstream code catches retrieval exceptions; preserve them as failures.
        if any(not record.get("ok") for record in searches):
            raise RuntimeError("native component retrieval failed during generation")
        code = state.get("selected_code")
        if not code:
            return {"disposition": "reject", "message": "Native workflow produced no scenario code"}
        if state.get("workflow_status") != "completed" or not isinstance(code, str):
            raise RuntimeError("native workflow has no complete scenario output")
        if redact(code) != code:
            raise RuntimeError("native artifact contains a configured credential; capture refused")
        with (root / "artifact.scenic").open("xb") as stream:
            stream.write(code.encode("utf-8"))
        write_json(native / "artifact-record.json", {
            "sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
            "bytes": len(code.encode("utf-8")),
            "source": "unmodified native selected_code",
        })
        return {"disposition": "generate"}
    finally:
        write_json(native / "retrieval.json", searches)
        write_json(native / "model-calls.json", model_calls)
        if workflow is not None:
            workflow.close()
        reset_agent_logger()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--input-json", action="store_true", help="standalone diagnostic input; common command adapter uses raw query text")
    parser.add_argument("--milvus-uri", default="http://127.0.0.1:19530")
    parser.add_argument("--embedding-model", default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--embedding-cache", type=Path)
    parser.add_argument("--embedding-catalog", type=Path)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument("--api-timeout", type=float, default=60.0)
    parser.add_argument("--api-max-retries", type=int, default=2)
    args = parser.parse_args()
    if not 0 <= args.temperature <= 2 or not 1 <= args.max_tokens <= 32768:
        parser.error("invalid model sampling profile")
    if not 0 < args.api_timeout <= 600 or not 0 <= args.api_max_retries <= 10:
        parser.error("invalid timeout/retry profile")
    sys.stderr = RedactedStream(sys.stderr)
    try:
        query = read_query(sys.stdin.buffer, args.input_json)
        with contextlib.redirect_stdout(sys.stderr):
            result = generate(query, args)
    except Exception as exc:
        failure = {"error_type": type(exc).__name__, "error": str(exc)}
        if Path("native").is_dir() and not (Path("native") / "failure.json").exists():
            write_json(Path("native") / "failure.json", failure)
        print(json.dumps(redact(failure)), file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
