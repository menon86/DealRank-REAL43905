"""Calculation engine — the grading-sensitive layer.

Imports nothing from app.api, app.models, or FastAPI. Plain dataclasses
(see types.py) in, plain dataclasses out, exercisable from a REPL with no
database. Money is Decimal; rates are Decimal fractions (6% is
Decimal("0.06")). The only float conversion in the codebase happens at the
IRR boundary in metrics.py, where numpy-financial requires it.

No ranking, hurdle, or sub-class-conditional branch belongs in this
package for Deliverable 2 — see ranking.py's module docstring.
"""
