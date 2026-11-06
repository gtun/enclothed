from contextlib import closing
from anthropic import Anthropic
from pathlib import Path
from enclothed.models import DEFAULT_LANGUAGE, InsightAnswer, Language, QueryResult, TokenUsage
from enclothed.llm import insights_turn, UnusableResponse
from enclothed.sandbox import build_snapshot, run_select
from enclothed import config
import json
from datetime import datetime, timezone


def add_usage(total: TokenUsage, usage: TokenUsage) -> TokenUsage:
    return TokenUsage(
        model = total.model,
        input_tokens = total.input_tokens + usage.input_tokens,
        output_tokens = total.output_tokens + usage.output_tokens,
        cache_creation_input_tokens = total.cache_creation_input_tokens + usage.cache_creation_input_tokens,
        cache_read_input_tokens = total.cache_read_input_tokens + usage.cache_read_input_tokens)


def tool_text(result: QueryResult) -> str:
    return result.error or json.dumps(
        {
            "columns" : result.columns,
            "rows" : result.rows
        },
        default=str,
        ensure_ascii=False,
    )


def log_insight(log_path: Path, user_id: int, usage: TokenUsage, message_count: int, question: str,
                answer: str | None, queries: list[str], error: str | None) -> None:
    """One line per question, including failed ones, so their tokens still count."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "user_id": user_id,
        "usage": usage.model_dump(),
        "messages": message_count,
        "question": question,
        "answer": answer,
        "sql": queries,
        "error": error,
    }
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def answer_question(client: Anthropic, db_path: Path, user_id: int, question: str, history: list[dict], language: Language = DEFAULT_LANGUAGE, preferences: str | None = None, log_path: Path | None = None) -> InsightAnswer:
    messages = [*history,
        {
            "role": "user",
            "content": question,
        }
    ]
    total_usage = TokenUsage(model=config.CLAUDE_MODEL, input_tokens=0, output_tokens=0)
    queries = []
    answer = None
    error = None

    try:
        with closing(build_snapshot(db_path, user_id)) as conn:
            tools = {"run_select": lambda sql: run_select(conn, sql)}

            for _ in range(config.INSIGHTS_MAX_TURNS):
                response, new_usage = insights_turn(client, messages, language, preferences)

                total_usage = add_usage(total_usage, new_usage)

                if response.stop_reason != "tool_use":
                    answer = "".join(block.text for block in response.content if block.type == "text").strip()
                    if not answer:
                        raise UnusableResponse(f"No answer in response (stop_reason={response.stop_reason})", total_usage)
                    return InsightAnswer(answer=answer, queries=queries, usage=total_usage)

                messages.append({"role": "assistant", "content": response.content})

                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    try:
                        result = tools[block.name](**block.input)
                    except (KeyError, TypeError):
                        result = QueryResult(error=f"Couldn't run tool {block.name} with those arguments.")

                    if not result.error:
                        queries.append(block.input["sql"])

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_text(result),
                        "is_error": result.error is not None,
                    })

                messages.append({"role": "user", "content": tool_results})

            raise UnusableResponse("Ran out of turns", total_usage)

    except Exception as caught:
        error = type(caught).__name__
        raise

    finally:
        if log_path:
            log_insight(log_path, user_id, total_usage, len(history) + 1, question, answer, queries, error)
