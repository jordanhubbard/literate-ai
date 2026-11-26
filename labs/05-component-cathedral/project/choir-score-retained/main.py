"""Export the exact browser choir score without Web Audio or a DOM."""
import json
import sys

NOTES = ("110", "146.8", "164.8", "220", "293.7")
INTERVAL_MS = 360

def query(arguments):
    if arguments == ["score"]:
        return {"frequencies_hz": list(NOTES), "interval_ms": INTERVAL_MS}
    if arguments == ["notes"]:
        return list(NOTES)
    if arguments == ["interval"]:
        return INTERVAL_MS
    raise ValueError("choose score, notes, or interval")

def run():
    arg = sys.argv[1]
    if arg == "--litai-test":
        from tests import litai_test
    elif arg == "--litai-smoke":
        print(json.dumps(query(["score"]), separators=(",", ":")))
    else:
        print(json.dumps(query(json.loads(arg)), separators=(",", ":")))

if __name__ == "__main__":
    run()
