import json
from pathlib import Path

from run import OUTPUTS, QUESTIONS, is_correct
from strategies import s3_tools

IDS = ["Q-01", "Q-03", "Q-08", "Q-09", "Q-17"]
VAGUE = "Looks things up."

rows = []
for question in QUESTIONS:
    if question["id"] not in IDS:
        continue
    result = s3_tools(question["question"], lookup_description=VAGUE)
    result["id"] = question["id"]
    result["correct"] = is_correct(result["answer"], question)
    rows.append(result)
    print(question["id"], result["answer"], "tool calls:", result["tool_calls"], "rounds:", result["rounds"],
          "OK" if result["correct"] else "X")

OUTPUTS.mkdir(exist_ok=True)
(OUTPUTS / "c1_vague.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
