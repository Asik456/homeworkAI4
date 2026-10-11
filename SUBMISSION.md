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

<!-- what changed in your plan, and why. "None" is an answer too. -->

### B2 — Tests

```text
<!-- pytest output -->
```

### B3 — The loop

- Round limit, and why:
- Where the logs are:
- Real Q-09 conversation compared with my A3 version, what is different:

### B4 — Three strategies

**What I kept the same:**

<!-- model, temperature, k, prompts, answer format, anything else -->

**My rule for a correct answer** (written before the first full run):

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | | | | | | | |
| 1 | S2 think and vote (k = ) | | | | | | | |
| 1 | S3 tools | | | | | | | |
| 2 | S1 direct | | | | | | | |
| 2 | S2 think and vote (k = ) | | | | | | | |
| 2 | S3 tools | | | | | | | |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | | | |
| Q-02 | | | |
| Q-03 | | | |
| Q-04 | | | |
| Q-05 | | | |
| Q-06 | | | |
| Q-07 | | | |
| Q-08 | | | |
| Q-09 | | | |
| Q-10 | | | |
| Q-11 | | | |
| Q-12 | | | |
| Q-13 | | | |
| Q-14 | | | |
| Q-15 | | | |
| Q-16 | | | |
| Q-17 | | | |
| Q-18 | | | |
| Q-19 | | | |
| Q-20 | | | |

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| | | | | |

### C2 — Three mistakes explained

### C3 — Which strategy I would use, and what would change it

### C4 — How sure I can be

### Final questions

1.
2.
3.
4.
5.
6.
7.
8.
