import json
import os
import re
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from tools import make_tools, run_tool

load_dotenv(Path(__file__).parent / ".env")

MODEL = "openai/gpt-5.6-luna"
RATE_IN = 0.20
RATE_OUT = 1.20
K = 5
TEMPERATURE = 1.0
MAX_ROUNDS = 12

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])

CORPUS = Path(__file__).parent / "data" / "corpus.jsonl"
DOCS = "\n\n".join(
    f"[{d['id']}] {d['title']}\n{d['text']}"
    for d in (json.loads(line) for line in CORPUS.read_text(encoding="utf-8").splitlines())
)

ANSWER_FORMAT = (
    "End your reply with one last line exactly like this:\n"
    "ANSWER: <district name or yes/no> | <number>\n"
    "Write the number without units and without commas, rounded to 3 decimal places."
)

S1_SYSTEM = "Answer the question using only the documents. Give only the final line, no explanation.\n" + ANSWER_FORMAT
S2_SYSTEM = (
    "Answer the question using only the documents. Think step by step: "
    "write the facts you use, then each calculation, then the result.\n" + ANSWER_FORMAT
)
S3_SYSTEM = (
    "Answer the question about the Nine Rivers Region. You do not have the documents: "
    "use the lookup tool for every fact and the calculate tool for all arithmetic.\n" + ANSWER_FORMAT
)


def ask(messages, **settings):
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        extra_body={"provider": {"allow_fallbacks": False}},
        **settings,
    )
    usage = response.usage
    return response.choices[0].message, usage.prompt_tokens, usage.completion_tokens


def parse_answer(text):
    found = re.findall(r"ANSWER:\s*(.+?)\s*\|\s*(-?[\d,]*\.?\d+)", text or "")
    if not found:
        return None
    name, number = found[-1]
    return name.strip().strip("*").strip(), float(number.replace(",", ""))


def with_documents(question):
    return f"Documents:\n\n{DOCS}\n\nQuestion: {question}"


def s1_direct(question):
    messages = [
        {"role": "system", "content": S1_SYSTEM},
        {"role": "user", "content": with_documents(question)},
    ]
    message, tokens_in, tokens_out = ask(messages)
    return {
        "answer": parse_answer(message.content),
        "text": message.content,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "calls": 1,
    }


def s2_vote(question):
    messages = [
        {"role": "system", "content": S2_SYSTEM},
        {"role": "user", "content": with_documents(question)},
    ]
    samples = []
    tokens_in = 0
    tokens_out = 0
    for _ in range(K):
        message, used_in, used_out = ask(messages, temperature=TEMPERATURE)
        tokens_in += used_in
        tokens_out += used_out
        samples.append({"answer": parse_answer(message.content), "text": message.content})

    votes = Counter(
        (s["answer"][0].lower(), s["answer"][1]) for s in samples if s["answer"] is not None
    )
    answer = None
    if votes:
        (name, number), count = votes.most_common(1)[0]
        answer = (name, number)
    return {
        "answer": answer,
        "votes": [[list(key), count] for key, count in votes.most_common()],
        "samples": samples,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "calls": K,
    }


def s3_tools(question, lookup_description=None):
    tools = make_tools(lookup_description) if lookup_description else make_tools()
    messages = [
        {"role": "system", "content": S3_SYSTEM},
        {"role": "user", "content": question},
    ]
    log = []
    tokens_in = 0
    tokens_out = 0
    for round_number in range(1, MAX_ROUNDS + 1):
        message, used_in, used_out = ask(messages, tools=tools)
        tokens_in += used_in
        tokens_out += used_out
        log.append({"round": round_number, "input_tokens": used_in, "output_tokens": used_out})

        if not message.tool_calls:
            log.append({"final_text": message.content})
            return {
                "answer": parse_answer(message.content),
                "text": message.content,
                "rounds": round_number,
                "tool_calls": sum(1 for item in log if "tool" in item),
                "log": log,
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
                "calls": round_number,
            }

        messages.append(message.model_dump(exclude_none=True))
        for call in message.tool_calls:
            start = time.perf_counter()
            result = run_tool(call.function.name, call.function.arguments)
            seconds = time.perf_counter() - start
            log.append({
                "round": round_number,
                "id": call.id,
                "tool": call.function.name,
                "arguments": call.function.arguments,
                "result": result,
                "seconds": round(seconds, 6),
            })
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

    return {
        "answer": None,
        "text": "stopped: round limit reached",
        "rounds": MAX_ROUNDS,
        "tool_calls": sum(1 for item in log if "tool" in item),
        "log": log,
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "calls": MAX_ROUNDS,
    }


STRATEGIES = {"S1": s1_direct, "S2": s2_vote, "S3": s3_tools}
