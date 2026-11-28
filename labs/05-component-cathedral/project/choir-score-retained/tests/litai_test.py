"""Check the authored provider's three supported queries."""
import json
from main import query

notes = ["110", "146.8", "164.8", "220", "293.7"]
expected = {
    "score": {"frequencies_hz": notes, "interval_ms": 360},
    "notes": notes,
    "interval": 360,
}
cases = []
for name, result in expected.items():
    assert query([name]) == result, name
    cases.append({"case_id": "choir-" + name, "outcome": "passed"})
print(json.dumps({"schema": "literate-ai/generated-test-results@1", "cases": cases}))
