"""Bounded-memory JSON envelope discrimination on an already selected descriptor.

This is not a JSON decoder or admission API. It keeps only schema/result/bundle
fields through three object levels; the caller must decode the same stable bytes
with the original schema's decoder. Legacy duplicate-last-key semantics survive.
"""

import codecs
import json
import os


class _Tokens:
    def __init__(self, descriptor, size, encoding):
        self.descriptor, self.remaining = descriptor, size
        self.decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
        self.chunk, self.cursor = "", 0

    def peek(self):
        while self.cursor == len(self.chunk):
            if not self.remaining:
                return None
            raw = os.read(self.descriptor, min(65536, self.remaining))
            if not raw:
                raise ValueError("bundle shortened during schema scan")
            self.remaining -= len(raw)
            self.chunk = self.decoder.decode(raw, final=not self.remaining)
            self.cursor = 0
        return self.chunk[self.cursor]

    def take(self):
        value = self.peek()
        if value is not None:
            self.cursor += 1
        return value

    def next(self):
        while self.peek() in ("\t", "\n", "\r", " "):
            self.take()
        value = self.take()
        if value is None:
            return "end", None
        if value in "{}[]:,":
            return value, None
        if value == '"':
            raw, overflow, escaped = ['"'], False, False
            while True:
                value = self.take()
                if value is None:
                    raise ValueError("unterminated bundle string")
                if len(raw) < 512:
                    raw.append(value)
                else:
                    overflow = True
                if value == '"' and not escaped:
                    break
                escaped = value == "\\" and not escaped
            # Relevant discriminants need at most 6 JSON characters per character.
            # Longer strings cannot equal a schema/key; retain no payload bytes.
            return "string", None if overflow else json.loads("".join(raw))
        while self.peek() is not None and self.peek() not in " \t\r\n{}[]:,":
            self.take()
        return "scalar", None


def scan_bundle_envelopes(descriptor, size, *, encoding="utf-8"):
    """Scan at most the original size with fixed token/payload memory ceilings.

    JSON grammar/depth are checked structurally here. Full scalar/UTF-8 validation
    belongs to the same-byte decoder. No array elements or unrelated field values
    are retained, and at most three levels of the finite envelope tree survive.
    """
    tokens = _Tokens(descriptor, size, encoding)
    stack, result, complete = [], None, False
    keys = {"schema", "result", "bundle"}
    while True:
        kind, value = tokens.next()
        if kind == "end":
            if stack or not complete:
                raise ValueError("incomplete bundle envelope")
            return result
        if complete and not stack:
            raise ValueError("trailing bundle envelope data")
        if stack:
            frame = stack[-1]
            state = frame[1]
            if state == "colon":
                if kind != ":":
                    raise ValueError("bundle key requires colon")
                frame[1] = "value"
                continue
            if state in ("key", "first-key"):
                if kind == "}" and state == "first-key":
                    stack.pop()
                    continue
                if kind != "string":
                    raise ValueError("bundle object key required")
                frame[1], frame[2] = "colon", value
                continue
            if state == "comma":
                closing = "}" if frame[0] == "object" else "]"
                if kind == closing:
                    stack.pop()
                    continue
                if kind != ",":
                    raise ValueError("bundle separator required")
                frame[1] = "key" if frame[0] == "object" else "value"
                continue
            if state == "first-value" and kind == "]":
                stack.pop()
                continue
            keep = frame[0] == "object" and frame[3] is not None and frame[2] in keys
        else:
            frame, keep = None, True
            complete = True
        child = {} if kind == "{" and keep and len(stack) < 3 else None
        retained = child if kind == "{" else value if kind == "string" else None
        if frame is None:
            result = retained
        else:
            if keep:
                frame[3][frame[2]] = retained
            frame[1] = "comma"
        if kind in ("{", "["):
            if len(stack) >= 1024:
                raise ValueError("bundle nesting exceeds JSON decoder bound")
            stack.append(
                [
                    "object" if kind == "{" else "array",
                    "first-key" if kind == "{" else "first-value",
                    None,
                    child,
                ]
            )
        elif kind not in ("string", "scalar"):
            raise ValueError("bundle value required")
