# HW4 — submission

**Name:** Askar Zhurabekov
**Student ID:** 67529
**Group:** 9
**Repository:** https://github.com/Asik456/homeworkAI4

**AI assistance:** I used Claude Code (Anthropic) to help me write the plan in Part A, write the code (tools, loop, strategies, tests), run it, and write the text of this file from my outputs. I read the documents and the plan myself and I checked the Q-09 numbers by hand.

**Model note:** I do not have an OpenAI key. I use the same model, `gpt-5.6-luna`, through OpenRouter (`openai/gpt-5.6-luna`). The code is the same OpenAI client with a different `base_url`.

---

## Part A — Plan on paper (Easy)

> Commit this whole part before any `.py` file exists.

### A1 — The steps

| # | Step | What goes in (types) | What comes out (types) | When it goes wrong | Tool, loop, or model? |
|---|---|---|---|---|---|
| 1 | **Read the question** | question: `str` | district names: `list[str]`; facts needed: `list[str]` (for example `population_2025`, `area_km2`); the formula: `str` (for example density = population / area) | The question uses a word that is not a field (for example "size"): the model must choose the closest field. | model |
| 2 | **Find the district** | name: `str` (maybe misspelled) | the exact district name: `str` | No district with this name → error with the closest names ("did you mean Ossbridge or Ossford?"). Two close names → never guess, return both in the error. | tool (`lookup`, inside it) |
| 3 | **Get one fact** | district: `str`, field: `str` | `{"value": float, "unit": str, "source": str}` | Unknown field → error with the list of fields. The number cannot be read → error, not a guess. Unknown unit → error. | tool (`lookup`) |
| 4 | **Do the arithmetic** | expression: `str` (for example `"44675 / 921.4"`) | `{"result": float}` | Not arithmetic, division by zero, too big number → `{"error": str}`, never a crash. | tool (`calculate`) |
| 5 | **Compare and choose** | two or three results: `float` | the winner: `str` (name or `yes`/`no`); the difference: `float` | The model must not compare numbers "by eye": the difference is again a `calculate` call. | model (+ `calculate`) |
| 6 | **Write the final line** | winner: `str`, difference: `float` | `"ANSWER: <name or yes/no> \| <number>"`: `str` | The model forgets the line or adds units → my scorer marks it as not answered. | model |
| 7 | **Run the requests** | the model message with `tool_calls` | one `{"role": "tool", "tool_call_id": ..., "content": str}` for every call | `arguments` is not valid JSON or has wrong keys → send an error result, do not run the tool. Too many rounds → stop, question is "unanswered". | loop (my code) |
| 8 | **Check the answer** | the final line: `str`, the row from `questions.json` | correct: `bool` | No `ANSWER:` line → unanswered. | my scorer code (not the model) |

**How the steps connect:**

```text
question (str)
   │
   ▼
[1 model: read the question] ──► for each district and field:
                                   [2 find district] ─► [3 get fact]   (lookup tool)
                                          │                    │
                                       error ◄─────────────────┘ value + unit + source
                                          │
   ┌──────────────────────────────────────┘
   ▼
[4 calculate] (one call per formula: density, per resident, difference ...)
   │
   ▼
[5 model: compare] ─► [4 calculate the difference] ─► [6 model: ANSWER line]
                                                          │
                                                          ▼
                                                 [8 scorer: correct or not]

[7 loop] sits between the model and the tools in every round:
model → tool_calls → loop runs the tools → tool results → model → ...
```

**What I am assuming:**

- **Year:** "2025" means the 2025 census, the 2025 budget and the water use in calendar 2025 (NR-00 says so). Schools and pupils are 2025/26.
- **Archived profiles:** NR-13 and NR-14 (ARCHIVED 2019) are never used. `lookup` skips any document with `ARCHIVED` in its title.
- **Corrections:** a correction notice wins over the profile (NR-00 says so). For Brightwater the area is **921.4**, not 912.4 (NR-16). `lookup` applies this itself and names both documents in `source`.
- **Units:** water is in megalitres. Lindenmoor gives cubic metres (2,151,400 m³). `lookup` converts it: 1 megalitre = 1,000 m³ (NR-15), so 2,151.4 megalitres, and it says it converted.
- **Water price:** 142.35 tenge per m³ in 2025, the same in every district (NR-15). Water cost = megalitres × 1,000 × 142.35.
- **Litres per resident per day:** megalitres × 1,000,000 / residents / 365 (2025 is not a leap year).
- **Growth in percent:** (2025 − 2020) / 2020 × 100.
- **Rounding:** never in the middle. Only the final number is rounded, and only by the model in the final line. Tools return full numbers.

**The assumption my answer is most sensitive to:** which figure is the current one. In Q-09, with the typo area (912.4) Millbrook wins by only 0.08; with the corrected area (921.4) it wins by 0.56. The winner stays the same, but the number is wrong. So the correction rule must live inside `lookup`, not in the model's memory.

### A2 — The two tools

#### `lookup`

```json
{
  "type": "function",
  "function": {
    "name": "lookup",
    "description": "Get ONE number about ONE district of the Nine Rivers Region from the official 2025 profiles. Archived 2019 profiles are never used, and correction notices are already applied. Water is always returned in megalitres (converted if the profile used cubic metres). Returns {district, field, value, unit, source}. Fields: population_2025, population_2020, area_km2, budget_million_tenge, water_megalitres (household water use in 2025), schools, pupils (2025/26), road_km (paved road), founded_year, water_tariff_tenge_per_m3 (2025 price, the same in every district). District names must be exact; if a name is wrong you get an error with close names.",
    "parameters": {
      "type": "object",
      "properties": {
        "district": {"type": "string", "description": "District name, for example Ossbridge"},
        "field": {"type": "string", "enum": ["population_2025", "population_2020", "area_km2", "budget_million_tenge", "water_megalitres", "schools", "pupils", "road_km", "founded_year", "water_tariff_tenge_per_m3"]}
      },
      "required": ["district", "field"],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| success | `{"district": "Brightwater", "field": "area_km2", "value": 921.4, "unit": "km2", "source": "NR-05, corrected by NR-16"}` |
| misspelled name (`Ossbrige`) | `{"error": "no district named Ossbrige; did you mean Ossbridge or Ossford?"}` |
| name not like any district (`Paris`) | `{"error": "no district named Paris; districts are: Ossbridge, Ossford, ..."}` |
| unknown field (`size`) | `{"error": "unknown field size; fields are: population_2025, ..."}` |
| field missing in the profile / number not readable | `{"error": "field road_km not found in NR-xx"}` |
| wrong type of input (not a string) | `{"error": "district and field must be strings"}` |

**Worst thing it could do with strange or dangerous input:** not much. It only reads one file that I choose, it never opens a path from the model, and it never runs anything. The worst real risk is a **wrong number**: if it used the archived profile or forgot the correction, the model would get a wrong fact that looks correct. That is why archived and corrected data is handled inside the tool. It also returns only one number, so a strange input cannot make it send a whole document.

#### `calculate`

```json
{
  "type": "function",
  "function": {
    "name": "calculate",
    "description": "Evaluate ONE arithmetic expression and return the exact result. Allowed: numbers, + - * / ** and parentheses. No names, no functions, no commas inside numbers (write 44675, not 44,675). The result is not rounded. Use this tool for ALL arithmetic, even small sums.",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {"type": "string", "description": "For example (37203 / 758.6) - (44675 / 921.4)"}
      },
      "required": ["expression"],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| success | `{"expression": "48317 * 1.0947", "result": 52892.6199}` |
| division by zero | `{"error": "division by zero"}` |
| not arithmetic (`__import__('os')...`, `(1).__class__`) | `{"error": "not allowed: only numbers and + - * / ** ( )"}` |
| too big (`9**9**9`) | `{"error": "number too big"}` (exponent limit and result limit, checked before computing) |
| syntax error (`2 +* 3`) | `{"error": "cannot read expression"}` |
| too long (more than 200 characters) | `{"error": "expression too long"}` |

**Worst thing it could do with strange or dangerous input:** if it used `eval`, the model could run any Python code on my computer (delete files, read my key). My `calculate` uses `ast`: it reads the expression as a tree and allows only numbers and the five operators, so code never runs. The second danger is a huge power like `9**9**9`, which would freeze the program; I block big exponents before computing.

### A3 — Q-09 by hand

Q-09: *Which district has the higher population density in 2025, Brightwater or Millbrook, and by how many residents per square kilometre?*

```json
[
  {"role": "system", "content": "You answer questions about the Nine Rivers Region. You do not have the documents: use lookup for facts and calculate for all arithmetic. End with: ANSWER: <name or yes/no> | <number>"},
  {"role": "user", "content": "Which district has the higher population density in 2025, Brightwater or Millbrook, and by how many residents per square kilometre?"},

  {"role": "assistant", "content": null, "tool_calls": [
    {"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Brightwater\", \"field\": \"population_2025\"}"}},
    {"id": "call_2", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Brightwater\", \"field\": \"area_km2\"}"}},
    {"id": "call_3", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Millbrook\", \"field\": \"population_2025\"}"}},
    {"id": "call_4", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Millbrook\", \"field\": \"area_km2\"}"}}
  ]},
  {"role": "tool", "tool_call_id": "call_1", "content": "{\"district\": \"Brightwater\", \"field\": \"population_2025\", \"value\": 44675, \"unit\": \"residents\", \"source\": \"NR-05\"}"},
  {"role": "tool", "tool_call_id": "call_2", "content": "{\"district\": \"Brightwater\", \"field\": \"area_km2\", \"value\": 921.4, \"unit\": \"km2\", \"source\": \"NR-05, corrected by NR-16\"}"},
  {"role": "tool", "tool_call_id": "call_3", "content": "{\"district\": \"Millbrook\", \"field\": \"population_2025\", \"value\": 37203, \"unit\": \"residents\", \"source\": \"NR-11\"}"},
  {"role": "tool", "tool_call_id": "call_4", "content": "{\"district\": \"Millbrook\", \"field\": \"area_km2\", \"value\": 758.6, \"unit\": \"km2\", \"source\": \"NR-11\"}"},

  {"role": "assistant", "content": null, "tool_calls": [
    {"id": "call_5", "type": "function", "function": {"name": "calculate", "arguments": "{\"expression\": \"37203 / 758.6 - 44675 / 921.4\"}"}}
  ]},
  {"role": "tool", "tool_call_id": "call_5", "content": "{\"expression\": \"37203 / 758.6 - 44675 / 921.4\", \"result\": 0.5556561156}"},

  {"role": "assistant", "content": "Millbrook is denser: 49.04 vs 48.49 residents per km2 (Brightwater area from the correction NR-16).\nANSWER: Millbrook | 0.6"}
]
```

**My arithmetic:**

- Brightwater: population 44,675 (NR-05). Area: NR-05 says 912.4, but NR-16 corrects it to **921.4**. Density = 44,675 / 921.4 = **48.486** residents per km².
- Millbrook: population 37,203, area 758.6 (NR-11). Density = 37,203 / 758.6 = **49.042** residents per km².
- Millbrook is higher. Difference = 49.042 − 48.486 = 0.5557 → rounded to 1 decimal: **0.6**. This is the same as `value` 0.6 in `questions.json`.
- Check of the trap: with the wrong area 912.4, Brightwater would be 48.964 and the difference only 0.08 → 0.1, a wrong answer.

### A4 — Why I split it this way

**Another way:** a `search` tool that takes a phrase (for example "Brightwater area") and returns the matching sentences from the documents, and the model reads the numbers from the sentences.

**Why I did not choose it:**

1. The traps would move to the model. The model would see "912.4" in the profile and maybe never search for the correction notice. It would see "2,151,400 cubic metres" and must remember to convert. With my `lookup`, these rules are in code, so they are the same every time.
2. Sentences are more tokens than one number, and every tool result is sent again in every next round of the loop.
3. Reading "44,675" from a sentence (with a comma) and typing it into `calculate` is one more place for a mistake.

The cost of my choice: `lookup` only knows the ten fields I wrote. A question about something else (for example "which river") cannot be answered. For these twenty questions all needed facts are in the ten fields, so I accept this.

I also did not choose **one tool per calculation** (`density`, `per_resident`, ...): it would need many tools, every tool definition costs tokens in every request, and a new kind of question would need a new tool. One `calculate` covers all of them.

---

## Part B — Build it and run it (Medium)

### What I changed from Part A while coding

The tools are the same as in A2 (the same names, descriptions and fields). Small changes:

- **Rounding (A1 step 6):** in Part A the model rounds the final number. While coding I asked the model to always give **3 decimals**, and my scorer rounds it to the question's `decimals`. Reason: the model does not know how many decimals each question wants, and I must not put the answer (or its format) into the prompt.
- **Checking `arguments` (A1 step 7):** `run_tool` in `tools.py` accepts only exactly the keys of each tool (`district` + `field`, or `expression`). Anything else gets an error result, the tool does not run.
- **`calculate` limits:** I added a limit of 200 characters, a result limit of 10^15, and I refuse complex numbers (for example `(-8)**0.5`).
- **Round limit:** 12 (explained in B3).

### B2 — Tests

15 tests in `tests/test_tools.py` (8 for `lookup`, 7 for `calculate`), no API key needed. Saved in `outputs/pytest.txt`.

```text
============================= test session starts ==============================
platform darwin -- Python 3.9.6, pytest-8.4.2, pluggy-1.6.0 -- homeworkAI4/.venv/bin/python
cachedir: .pytest_cache
rootdir: homeworkAI4
plugins: anyio-4.12.1
collecting ... collected 15 items

tests/test_tools.py::test_lookup_finds_2025_population PASSED            [  6%]
tests/test_tools.py::test_lookup_misspelled_name PASSED                  [ 13%]
tests/test_tools.py::test_lookup_similar_names_are_not_mixed PASSED      [ 20%]
tests/test_tools.py::test_lookup_skips_archived_profile PASSED           [ 26%]
tests/test_tools.py::test_lookup_applies_correction PASSED               [ 33%]
tests/test_tools.py::test_lookup_converts_cubic_metres PASSED            [ 40%]
tests/test_tools.py::test_lookup_unknown_field_and_district PASSED       [ 46%]
tests/test_tools.py::test_lookup_bad_input_does_not_crash PASSED         [ 53%]
tests/test_tools.py::test_calculate_multiplication PASSED                [ 60%]
tests/test_tools.py::test_calculate_refuses_import PASSED                [ 66%]
tests/test_tools.py::test_calculate_refuses_class PASSED                 [ 73%]
tests/test_tools.py::test_calculate_refuses_huge_power_fast PASSED       [ 80%]
tests/test_tools.py::test_calculate_division_by_zero PASSED              [ 86%]
tests/test_tools.py::test_calculate_brackets_and_order PASSED            [ 93%]
tests/test_tools.py::test_calculate_bad_syntax_and_commas PASSED         [100%]

============================== 15 passed in 0.02s ==============================
```

### B3 — The loop

- **Round limit, and why:** 12 rounds (`MAX_ROUNDS` in `strategies.py`). The biggest questions (Q-11, Q-20) need 6 lookups and 4 calculations = 10 tool calls. If the model asked for only one call per round, that is 10 rounds + 1 round for the final answer = 11. 12 gives one spare round. More rounds would only let a broken loop spend more tokens, because every round re-sends the whole conversation. In my runs the model asked for many calls in one round, so the most it ever used was **4 rounds** (Q-19 in run 1, Q-07, Q-15 in run 2, Q-20 in both). No question hit the limit.
- **Where the logs are:** `outputs/logs/run1/Q-XX.json` and `outputs/logs/run2/Q-XX.json` — one file per question. Each tool call has its round, `id`, tool name, `arguments` (the raw string), result and seconds; each round has its input and output tokens. All results per strategy are in `outputs/run1_S1.json`, `outputs/run1_S2.json`, ... (S2 also keeps all 5 samples and the votes).
- **Real Q-09 conversation compared with my A3 version, what is different** (`outputs/logs/run1/Q-09.json`):
  - **The same:** round 1 asked for exactly my 4 lookups in one turn, and the tool returned 921.4 with `"source": "NR-05, corrected by NR-16"`. The answer was right: `ANSWER: Millbrook | 0.556` (→ 0.6).
  - **Different 1:** in round 2 the model asked for **3** calculations, not 1: `44675 / 921.4`, `37203 / 758.6`, and then the difference again in one expression. So 7 tool calls, not 5 — it wanted both densities to write in its answer.
  - **Different 2:** it subtracted in the other order, `(44675 / 921.4) - (37203 / 758.6)` = **−0.5557**, and then wrote the positive number itself.
  - **Different 3:** each round cost more input tokens: 475 → 795 → 989, because each round re-sends all earlier tool results.

### B4 — Three strategies

**What I kept the same:**

- Model: `openai/gpt-5.6-luna` through OpenRouter, with `allow_fallbacks: false` (so no other model can answer).
- The same 20 questions from `data/questions.json`, in the same order.
- The same answer format for all three strategies: the last line is `ANSWER: <district name or yes/no> | <number>`, number without units and commas, rounded to 3 decimals (`ANSWER_FORMAT` in `strategies.py`).
- The same scorer (`is_correct` in `run.py`) for all three.
- The same documents for S1 and S2: all 17 documents, in file order, in the user message. S3 gets no documents, only the two tools.
- k = 5 for S2, with `temperature = 1.0`. S1 and S3 use the default settings (no temperature set).
- S3: round limit 12. Same tool definitions in every question.
- Cost is computed with the luna price on OpenRouter: $0.20 per million input tokens and $1.20 per million output tokens. Tokens come from `usage` of every call (all 5 samples in S2, every round in S3).

**My rule for a correct answer** (written before the first full run):

- The name must be the same as `answer` (not case-sensitive). For yes/no questions it must be `yes` or `no`.
- I round the model's number to `decimals` of the question. It is correct when it is equal to `value`, or different by 1 in the last digit (for example `value` 0.6: 0.5, 0.6 and 0.7 are accepted).
- No `ANSWER:` line, or a strategy that stops (round limit or error) → **unanswered**, and it counts as wrong.

**Why 20 questions and this rule:** 20 is all the questions the homework gives, and each one needs 2–3 facts and 1–4 calculations, so all of them test the same multi-step skill. Running 2 full runs is about $0.13 each, so I could repeat it. The rule checks the name exactly (a wrong district is a wrong answer, even with the right number) and allows ±1 in the last digit, because a correct method can round differently in the middle (for example S1 gave 1.692 and S3 gave 1.687 on Q-02; both are 1.69).

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | 18 | 0 | 43,619 | 5,193 | 4.56 | 92.9 | 0.0150 |
| 1 | S2 think and vote (k = 5) | 20 | 0 | 219,095 | 43,652 | 24.05 | 537.4 | 0.0962 |
| 1 | S3 tools | 20 | 0 | 47,084 | 6,180 | 8.50 | 166.6 | 0.0168 |
| 2 | S1 direct | 20 | 0 | 43,619 | 5,505 | 4.02 | 93.6 | 0.0153 |
| 2 | S2 think and vote (k = 5) | 18 | 0 | 219,095 | 45,452 | 26.08 | 550.1 | 0.0984 |
| 2 | S3 tools | 19 | 0 | 48,151 | 6,153 | 8.27 | 164.4 | 0.0170 |

Source: `outputs/run1_*.json`, `outputs/run2_*.json` (the `summary` of each file), printed by `python run.py 1` and `python run.py 2` (`outputs/run1_console.txt`, `outputs/run2_console.txt`).

**What the full assignment cost me:** my computed cost for everything (test run, 2 full runs, C1) is **$0.278**. My OpenRouter account usage went up by **$0.203** for all of HW3 and HW4 together. The real bill is lower than my formula, probably because OpenRouter/OpenAI cache the long repeated prefix (the 17 documents are the same in every S1/S2 call) and charge cached input tokens less — the Week 4 "stable prefix is money" idea. My table uses the list price, so it is the upper bound.

**About temperature:** OpenRouter does not list `temperature` as a supported parameter for `openai/gpt-5.6-luna` (it is a reasoning model). I sent `temperature = 1.0` for S2 and the call did not fail, but I cannot be sure it was used. The 5 samples **did** vary (for example Q-05 in run 2 gave 5 different numbers), so voting had something to vote on.

**Note about S1:** luna is a reasoning model, so even S1 ("give only the final line") thinks privately before answering: 5,193 output tokens for 20 one-line answers, about 260 per question. So S1 is "no visible reasoning, one sample", not "no reasoning".

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | ✓ | ✓ | ✓ |
| Q-02 | ✓ | ✓ | ✓ |
| Q-03 | ✓ | ✓ | ✓ |
| Q-04 | ✓ | ✓ | ✓ |
| Q-05 | ✗ (4235.315) | ✓ | ✓ |
| Q-06 | ✓ | ✓ | ✓ |
| Q-07 | ✓ | ✓ | ✓ |
| Q-08 | ✓ | ✓ | ✓ |
| Q-09 | ✓ | ✓ | ✓ |
| Q-10 | ✓ | ✓ | ✓ |
| Q-11 | ✓ | ✓ | ✓ |
| Q-12 | ✓ | ✓ | ✓ |
| Q-13 | ✓ | ✓ | ✓ |
| Q-14 | ✓ | ✓ | ✓ |
| Q-15 | ✓ | ✓ | ✓ |
| Q-16 | ✓ | ✓ | ✓ |
| Q-17 | ✓ | ✓ | ✓ |
| Q-18 | ✓ | ✓ | ✓ |
| Q-19 | ✗ (Redfen) | ✓ | ✓ |
| Q-20 | ✓ | ✓ | ✓ |

**Run 2 mistakes:** S1 none (20/20); S2 Q-05 (4235.314) and Q-12 (0.064); S3 Q-08 (72456.15).

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

I ran S3 again on 5 questions with the `lookup` description changed to `"Looks things up."` (`c1_vague.py`, results in `outputs/c1_vague.json`). Everything else is the same — also the JSON schema, so the model still sees the field names in the `enum`. "Yours" is run 1.

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| Q-01 | 5 | 5 | Ossbridge 4.57 ✓ | Ossbridge 4.57 ✓ |
| Q-03 | 5 | 7 | Lindenmoor 5.34 ✓ | Lindenmoor 5.34 ✓ |
| Q-08 | 4 | 5 | Brightwater 72.456 ✓ | **Brightwater 1.064 ✗** |
| Q-09 | 7 | 5 | Millbrook 0.556 ✓ | Millbrook 0.556 ✓ |
| Q-17 | 7 | 7 | Harrowfield 884.457 ✓ | Harrowfield 884.457 ✓ |

**What changed:** 4 of 5 answers stayed correct, because the field names in the schema (`population_2025`, `area_km2`, `water_megalitres`) still say a lot. But **Q-08 broke**. With my description, the model looked up `water_megalitres` for both districts. With the vague one, it never asked for water use: it asked for `population_2025` and the tariff, and calculated `(44675-37203)*142.35/1000000` = 1.064 — it used **the number of people as if it were the water used**. My description says `water_megalitres (household water use in 2025)` and "Water is always returned in megalitres"; the vague one says nothing, so the model guessed the meaning of the fields and guessed wrong. The answer still looks confident and has the right district.

**Why:** the description is part of the prompt (Week 5: "the description is the prompt"). The model decides which tool and which arguments to use only from the text I send. A shorter description is also cheaper (1,712 vs 2,201 input tokens on Q-01), but here it saved about 500 tokens and cost a wrong answer.

### C2 — Three mistakes explained

**S1 — Q-05, run 1: a lost digit.** The whole reply was one line: `ANSWER: Coldharbour | 4235.315`. The correct difference is 14,235.314 tenge per resident (207,495.398 − 193,260.083). The model lost the first digit "1". In run 2, S1 got the same question right (14235.314). **Why:** the model does not calculate; it writes numbers as tokens, and a long number is several tokens. A dropped token still looks like a normal number, and S1 has only **one** sample, so there is no second chance and no way to notice. This is the mistake a calculator removes: in S3 the subtraction was done by `calculate`, so Q-05 was correct in both runs.

**S2 — Q-12, run 2: voting cannot fix a repeated mistake.** The votes were `tarnvale 0.064` × 3 and `tarnvale 64.392` × 2, so the majority was wrong. The 3 wrong samples all did the same thing: "Harrowfield: 16,021.7 ÷ 13,904 = 1.152 thousand tenge per pupil" — they divided **million** tenge by pupils and called it **thousand** tenge, so they forgot × 1,000. The 2 right samples wrote "Since 1 million tenge = 1,000 thousand tenge". **Why:** voting reduces **random** errors (variance). When the samples make different random mistakes, the right answer is the most common one — this worked in run 1: Q-05 had `14235.314` × 3 against `4235.314` × 1, and Q-19 had `lindenmoor` × 3 against `redfen` × 2 (the name mistake S1 made). But voting cannot fix a **systematic** error (bias): if the model usually reads the units wrong, 5 samples repeat it, and the vote makes the wrong answer look sure.

Q-05 in run 2 shows a second weakness: the 5 samples gave **5 different** numbers (4235.314, 14235.315, 42235.314, 14195.137, 14235.314). With no majority, my code took the first one (wrong). My vote key used the 3-decimal number, so 14235.314 and 14235.315 counted as different answers, although both round to the correct 14235. A vote on the rounded number would have won 2–1–1–1. That is a design mistake in my voting, and I keep the result as it is.

**S3 — Q-08, run 2: the calculator does exactly what it is told.** From `outputs/logs/run2/Q-08.json`: the lookups were all correct (`3315`, `2806` megalitres, tariff `142.35`), then `calculate {"expression":"(3315-2806)*142.35"}` → `72456.15`, and the model wrote `72,456.150 million tenge`. The correct formula needs × 1,000 (megalitres → m³) and ÷ 1,000,000 (tenge → million tenge), so ÷ 1,000. In run 1, the same question gave `(3315-2806)*142.35/1000` → 72.456, correct. **Why:** `calculate` removes **arithmetic** errors, but the **formula** still comes from the model. Garbage in, exact garbage out. The good part: the log shows the exact expression, so I can see the mistake in one line; in S1 I cannot see where a wrong number came from.

**Why the loop needed that many rounds, and why each round costs more:** almost every question took 3 rounds: (1) all lookups in one turn, (2) the calculations, (3) the final answer. Q-20 took 4 rounds and 10 calls (6 lookups, 3 divisions, then one more subtraction). Input tokens per round in Q-20 (run 1): **488 → 962 → 1,204 → 1,295**. Each round re-sends the system message, the question, the 366 tokens of tool definitions, and **every earlier tool call and result**, because the model remembers nothing between calls.

### C3 — Which strategy I would use, and what would change it

**I would use S3 (tools).**

| | S1 direct | S2 vote (k = 5) | S3 tools |
|---|---:|---:|---:|
| Correct, both runs | 38/40 | 38/40 | **39/40** |
| Cost per 20 questions | $0.015 | $0.097 | $0.017 |
| Median seconds | 4.0–4.6 | 24–26 | 8.3–8.5 |

- **Why not S2:** it costs **6.4×** more than S1 and takes about 5.7× longer, and it was not more accurate in total (38/40, the same as S1). Voting fixed random mistakes (run 1: Q-05, Q-19) but made new ones when most samples repeated the same unit mistake (Q-12) or when all samples disagreed (Q-05, run 2).
- **Why not S1:** it is the cheapest and the fastest, and 38/40 is good. But its mistakes are invisible: it gives one number with no working, so a lost digit (Q-05) looks exactly like a correct answer. It also only works because all documents fit in the prompt (about 2,200 tokens).
- **Why S3:** the most correct (39/40), almost the same price as S1 ($0.017 vs $0.015), every fact has a `source`, the archived profiles and the correction are handled in code, and every calculation is exact and is in the log. Its one mistake (a wrong formula) is visible in one line of the log. It is slower than S1 (about 8 s vs 4 s), which is fine for this task.

**Situations that would change my choice:**
- **1,000× more documents:** still **S3** — even more. S1 and S2 would need about 2.3 million tokens per prompt, which does not fit in the window and would cost 1,000× more per call. S3 sends only the facts it asks for (`lookup` needs a search index then, see final question 6).
- **A strict time limit (for example under 5 seconds) and a tiny budget:** **S1** — median 4.0–4.6 s and the lowest cost, with 38/40.
- **Questions with no arithmetic** (like "which is older" or "what is the area"): **S1**. The calculator gives no benefit when there is nothing to compute; even Q-10 (one subtraction of years) was correct in all strategies.
- **Questions about facts that are not one of my 10 fields** (for example "which river"): **S1**, or S3 with a text-search tool, because my `lookup` cannot return them.

### C4 — How sure I can be

- **How different were my two runs?** With the same code, S1 went from 18 to 20, S2 from 20 to 18, and S3 from 20 to 19. So one strategy can move by **2 questions (10 points)** between runs with nothing changed. The mistakes were also on different questions (S1: Q-05, Q-19 in run 1, none in run 2).
- **Is the difference between my two best strategies bigger than that?** No. S3 had 39/40 and S1 had 38/40: **1 question** difference, smaller than the 2-question change between runs of the same strategy. So my numbers cannot prove that S3 is more accurate than S1. What they do show more strongly is the **cost** (S2 is 6.4× S1 in every run, because it is 5 calls by design) and the **kind** of mistakes: S3's mistakes are formula mistakes I can see in the log; S1's are arithmetic mistakes I cannot see.
- **How many questions would I need?** With 20 questions, one question is 5 points. For 19/20 (95%), a 95% interval is about ±10 points (√(0.95·0.05/20) ≈ 0.049, × 1.96). To see a difference of 2.5 points (39/40 vs 38/40) with 95% confidence, I estimate about **400–500 questions** per strategy (from √((0.0475 + 0.024)/n) · 1.96 < 0.025 → n ≈ 450), or many repeated runs. Also, my 20 questions are all the same type (compare two districts with a formula), from one model on one day, so the result may not hold for other question types.

### Final questions

1. **When the model sends a `tool_calls` message, what has actually run so far?** Nothing. The model only wrote text: a tool name and an `arguments` string, with an `id`. For example in Q-09, round 1 (475 input tokens) returned 4 `lookup` requests, and nothing was looked up until my `run_tool` ran them. My code decides whether to run, refuse or change them.

2. **Why does `arguments` arrive as a string, and what goes wrong if you pass it straight into your function?** The model can only produce tokens, so the arguments are JSON **text** it wrote, for example `'{"district":"Brightwater","field":"area_km2"}'`. If I pass this string straight in, `lookup` gets one string instead of two values (it would search for a district called `{"district":...`), and the text may also be broken JSON or have extra or missing keys. So `run_tool` first does `json.loads`, checks it is an object with exactly the right keys, and only then calls the tool; otherwise it returns an error result.

3. **How many tokens do your two tool definitions add to every S3 request?** I measured it (`measure_tools.py`, `outputs/measure_tools.txt`): the same "Say hi." message had `usage.prompt_tokens` 9 without tools and 375 with tools, so the tools add **366 tokens** to every request. (tiktoken on my JSON gives 444, because the API sends the tools in its own shorter format.) In run 1, S3 made 62 model calls, so the tool definitions were about 62 × 366 = **22,700 of the 47,084 input tokens — almost half**.

4. **How much more did S2 cost than S1?** Run 1: $0.0962 vs $0.0150 = **6.4×**. Input tokens: 219,095 vs 43,619 = **5.0×**, because S2 sends the same prompt with all documents 5 times (k = 5). Output tokens: 43,652 vs 5,193 = **8.4×**, more than 5×, because S2 also asks the model to write its reasoning step by step in every sample, while S1 asks for one line.

5. **Which question needed the most rounds in S3, and why?** **Q-20**: 4 rounds and 10 tool calls in both runs (Q-11 also had 10 calls but in 3 rounds). It compares three districts, so it needs 6 lookups (budget and population for each) and 3 divisions, then the model found the largest and smallest and asked for one more subtraction in a separate round. Its input grew 488 → 962 → 1,204 → 1,295 tokens, 3,949 in total, the most of all questions.

6. **What would you change in `lookup` if there were 100,000 documents?** Now `lookup` reads all documents when the program starts and finds the profile by the exact district name and a regular expression per field. With 100,000 documents I would build an **index once** (a table or database: district, field, value, unit, year, source, archived yes/no), so a lookup is one fast query. I would keep the archived and correction rules as columns, not as text the model must read. For questions that are not one of the fixed fields, I would add a **search** tool (BM25 or embeddings, like in HW3) that returns only the top few short passages with their ids, never whole documents.

7. **What stops your `calculate` from running dangerous code? Could the model still make it misbehave?** It never uses `eval` or `exec`. It reads the expression with `ast.parse` and walks the tree, and only allows number constants and `+ - * / **` (and a minus sign). A name, a function call or an attribute like `__import__` or `.__class__` is not in the list, so it is refused before anything runs (tests `test_calculate_refuses_import` and `test_calculate_refuses_class`). `9**9**9` is refused because the exponent is over 100, before computing (the test checks it takes less than 1 second). It also limits the length (200 characters) and the result (10^15). The model can still make it give a **wrong** answer with a correct-looking formula: in Q-08 (run 2) it sent `(3315-2806)*142.35` without the unit conversion, and `calculate` returned exactly that.

8. **For which kind of question did tools help most, and for which did they not help at all?** They helped most on questions with **long numbers and several steps**, like Q-05 (budget per resident, numbers around 200,000): S1 lost a digit in run 1 and S2 gave 5 different numbers in run 2, but S3 was correct in both runs because the calculator did the arithmetic. They also helped with the **traps**: the correction for Q-09 and the cubic metres for Q-03 were handled inside `lookup`. They did not help at all on simple questions like Q-06, Q-10 or Q-16 (one addition or subtraction): all three strategies were correct in both runs, and S3 just cost more time. And they did not help when the **formula** was wrong (Q-08 in S3, run 2), because the model still writes the formula.
