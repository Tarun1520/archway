"""
Policy: rules that must always hold, written as plain Python.

    stated_constraints.py  find hard limits in the user's own words
    conflicts.py           spot requirements that cannot all be true
    clarification.py       decide which questions are worth asking

None of these files calls a model. That is the point: a model may MISS a
constraint or a conflict, so the things we must not get wrong are checked by
code that behaves the same way every time and can be tested with certainty.

Learn more: LEARNING_GUIDE.md topic 38.
"""
