import json
import statistics
import sys
import time
from pathlib import Path

from strategies import K, MODEL, RATE_IN, RATE_OUT, STRATEGIES

QUESTIONS = json.loads((Path(__file__).parent / "data" / "questions.json").read_text(encoding="utf-8"))
OUTPUTS = Path(__file__).parent / "outputs"


def is_correct(answer, question):
    if answer is None:
        return False
    name, number = answer
    if name.lower() != question["answer"].lower():
        return False
    step = 10 ** -question["decimals"]
    return abs(round(number, question["decimals"]) - question["value"]) <= step + 1e-9


def run_strategy(run_id, strategy, questions):
    results = []
    for question in questions:
        start = time.perf_counter()
        try:
            result = STRATEGIES[strategy](question["question"])
        except Exception as error:
            result = {"answer": None, "error": repr(error), "input_tokens": 0, "output_tokens": 0, "calls": 0}
        result["seconds"] = round(time.perf_counter() - start, 2)
        result["id"] = question["id"]
        result["correct"] = is_correct(result["answer"], question)
        results.append(result)
        print(f"  {strategy} {question['id']}: {result['answer']} expected {question['answer']} | {question['value']}"
              f" -> {'OK' if result['correct'] else 'X'} ({result['seconds']}s)")

        if strategy == "S3":
            log_dir = OUTPUTS / "logs" / f"run{run_id}"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / f"{question['id']}.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    tokens_in = sum(r["input_tokens"] for r in results)
    tokens_out = sum(r["output_tokens"] for r in results)
    seconds = [r["seconds"] for r in results]
    summary = {
        "run": run_id,
        "strategy": strategy,
        "model": MODEL,
        "k": K if strategy == "S2" else None,
        "questions": len(results),
        "correct": sum(r["correct"] for r in results),
        "unanswered": sum(r["answer"] is None for r in results),
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "median_seconds": round(statistics.median(seconds), 2),
        "total_seconds": round(sum(seconds), 2),
        "cost_usd": round((tokens_in * RATE_IN + tokens_out * RATE_OUT) / 1_000_000, 4),
    }
    OUTPUTS.mkdir(exist_ok=True)
    (OUTPUTS / f"run{run_id}_{strategy}.json").write_text(
        json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main():
    run_id = sys.argv[1]
    strategies = [a for a in sys.argv[2:] if a in STRATEGIES] or list(STRATEGIES)
    ids = [a for a in sys.argv[2:] if a.startswith("Q-")]
    questions = [q for q in QUESTIONS if not ids or q["id"] in ids]

    summaries = [run_strategy(run_id, s, questions) for s in strategies]

    print("\n| Run | Strategy | Correct | Unanswered | Input tokens | Output tokens | Median s | Total s | Cost ($) |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for s in summaries:
        print(f"| {s['run']} | {s['strategy']} | {s['correct']}/{s['questions']} | {s['unanswered']} | {s['input_tokens']} "
              f"| {s['output_tokens']} | {s['median_seconds']} | {s['total_seconds']} | {s['cost_usd']} |")


if __name__ == "__main__":
    main()
