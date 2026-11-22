"""Run the standard-library initializer AST vectors on one native interpreter."""

from __future__ import annotations

import json
import sys

from tests.support.fixtures_initializer_ast import profile_vectors

if __name__ == "__main__":
    print(
        json.dumps(
            {
                "schema": "literate-ai/initializer-ast-probe@1",
                "python": sys.version.split()[0],
                "implementation": sys.implementation.name,
                "pairs": profile_vectors(),
            },
            sort_keys=True,
        )
    )
