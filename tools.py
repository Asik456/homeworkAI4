import ast
import difflib
import json
import operator
import re
from pathlib import Path

CORPUS = Path(__file__).parent / "data" / "corpus.jsonl"

PATTERNS = {
    "population_2025": [r"2025 census (?:recorded|counted) ([\d,]+)", r"([\d,]+) in 2025"],
    "population_2020": [r"2020 census had recorded ([\d,]+)", r"up from ([\d,]+) at the 2020 census", r"([\d,]+) in 2020"],
    "area_km2": [r"([\d,.]+) square kilometres"],
    "budget_million_tenge": [r"([\d,.]+) million tenge"],
    "water_megalitres": [r"([\d,]+) megalitres"],
    "schools": [r"(\d+) schools"],
    "pupils": [r"([\d,]+) pupils"],
    "road_km": [r"([\d,.]+) km of paved road", r"paved road network is ([\d,.]+) km"],
    "founded_year": [r"[Ff]ounded in (\d{4})"],
}

UNITS = {
    "population_2025": "residents",
    "population_2020": "residents",
    "area_km2": "km2",
    "budget_million_tenge": "million tenge",
    "water_megalitres": "megalitres",
    "schools": "schools",
    "pupils": "pupils",
    "road_km": "km",
    "founded_year": "year",
    "water_tariff_tenge_per_m3": "tenge per m3",
}


def to_number(text):
    number = float(text.replace(",", ""))
    if number.is_integer():
        return int(number)
    return number


def load_docs():
    profiles = {}
    corrections = {}
    tariff = None
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        doc = json.loads(line)
        title = doc["title"]
        if "ARCHIVED" in title:
            continue
        if " district profile" in title:
            name = title.split(" district profile")[0]
            profiles[name] = doc
        elif title.startswith("Correction notice"):
            name = title.split("-")[-1].strip()
            found = re.search(r"correct area is ([\d,.]+) square kilometres", doc["text"])
            if found:
                corrections[(name, "area_km2")] = (to_number(found.group(1)), doc["id"])
        elif "water tariff" in title:
            found = re.search(r"2025 the regional household water tariff is ([\d.]+) tenge", doc["text"])
            tariff = (to_number(found.group(1)), doc["id"])
    return profiles, corrections, tariff


PROFILES, CORRECTIONS, TARIFF = load_docs()


def find_district(name):
    for district in PROFILES:
        if district.lower() == name.strip().lower():
            return district, None
    close = difflib.get_close_matches(name.strip().title(), list(PROFILES), n=3, cutoff=0.5)
    if close:
        return None, f"no district named {name}; did you mean {' or '.join(close)}?"
    return None, f"no district named {name}; districts are: {', '.join(PROFILES)}"


def lookup(district, field):
    if not isinstance(district, str) or not isinstance(field, str):
        return {"error": "district and field must be strings"}
    if field not in UNITS:
        return {"error": f"unknown field {field}; fields are: {', '.join(UNITS)}"}
    name, error = find_district(district)
    if error:
        return {"error": error}

    if field == "water_tariff_tenge_per_m3":
        value, source = TARIFF
        return {"district": name, "field": field, "value": value, "unit": UNITS[field], "source": source}

    doc = PROFILES[name]
    source = doc["id"]
    value = None
    for pattern in PATTERNS[field]:
        found = re.search(pattern, doc["text"])
        if found:
            value = to_number(found.group(1))
            break

    if field == "water_megalitres" and value is None:
        found = re.search(r"([\d,]+) cubic metres", doc["text"])
        if found:
            value = to_number(found.group(1)) / 1000
            source = f"{doc['id']} (converted from cubic metres: 1 megalitre = 1,000 m3)"

    if (name, field) in CORRECTIONS:
        value, notice = CORRECTIONS[(name, field)]
        source = f"{doc['id']}, corrected by {notice}"

    if value is None:
        return {"error": f"field {field} not found in {doc['id']}"}
    return {"district": name, "field": field, "value": value, "unit": UNITS[field], "source": source}


OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

MAX_RESULT = 1e15


def walk(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
        return OPS[type(node.op)](walk(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        left = walk(node.left)
        right = walk(node.right)
        if isinstance(node.op, ast.Pow) and (abs(right) > 100 or abs(left) > 1e6):
            raise OverflowError
        if isinstance(node.op, ast.Div) and right == 0:
            raise ZeroDivisionError
        result = OPS[type(node.op)](left, right)
        if isinstance(result, complex):
            raise ValueError
        if abs(result) > MAX_RESULT:
            raise OverflowError
        return result
    raise ValueError


def calculate(expression):
    if not isinstance(expression, str):
        return {"error": "expression must be a string"}
    if len(expression) > 200:
        return {"error": "expression too long"}
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return {"error": "cannot read expression"}
    try:
        result = walk(tree.body)
    except ZeroDivisionError:
        return {"error": "division by zero"}
    except OverflowError:
        return {"error": "number too big"}
    except ValueError:
        return {"error": "not allowed: only numbers and + - * / ** ( )"}
    return {"expression": expression, "result": round(result, 10)}


LOOKUP_DESCRIPTION = (
    "Get ONE number about ONE district of the Nine Rivers Region from the official 2025 profiles. "
    "Archived 2019 profiles are never used, and correction notices are already applied. "
    "Water is always returned in megalitres (converted if the profile used cubic metres). "
    "Returns {district, field, value, unit, source}. "
    "Fields: population_2025, population_2020, area_km2, budget_million_tenge, "
    "water_megalitres (household water use in 2025), schools, pupils (2025/26), road_km (paved road), "
    "founded_year, water_tariff_tenge_per_m3 (2025 price, the same in every district). "
    "District names must be exact; if a name is wrong you get an error with close names."
)

CALCULATE_DESCRIPTION = (
    "Evaluate ONE arithmetic expression and return the exact result. "
    "Allowed: numbers, + - * / ** and parentheses. No names, no functions, "
    "no commas inside numbers (write 44675, not 44,675). The result is not rounded. "
    "Use this tool for ALL arithmetic, even small sums."
)


def make_tools(lookup_description=LOOKUP_DESCRIPTION):
    return [
        {
            "type": "function",
            "function": {
                "name": "lookup",
                "description": lookup_description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "district": {"type": "string", "description": "District name, for example Ossbridge"},
                        "field": {"type": "string", "enum": list(UNITS)},
                    },
                    "required": ["district", "field"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": CALCULATE_DESCRIPTION,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "For example (37203 / 758.6) - (44675 / 921.4)"},
                    },
                    "required": ["expression"],
                    "additionalProperties": False,
                },
            },
        },
    ]


def run_tool(name, arguments):
    try:
        args = json.loads(arguments)
    except (json.JSONDecodeError, TypeError):
        return {"error": "arguments are not valid JSON"}
    if not isinstance(args, dict):
        return {"error": "arguments must be a JSON object"}
    if name == "lookup":
        if set(args) != {"district", "field"}:
            return {"error": "lookup needs exactly two arguments: district and field"}
        return lookup(args["district"], args["field"])
    if name == "calculate":
        if set(args) != {"expression"}:
            return {"error": "calculate needs exactly one argument: expression"}
        return calculate(args["expression"])
    return {"error": f"unknown tool {name}"}
