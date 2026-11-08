# -*- coding: utf-8 -*-
"""Pruebas de numfix: py tests/test_numfix.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from numfix import NumberFixer


def words(*texts):
    return [(i * 50.0, 0.0, i * 50.0 + 40, 10.0, t) for i, t in enumerate(texts)]


def fixed(doc_langs, learn, *texts):
    f = NumberFixer(doc_langs)
    f.learn(words(*(learn or texts)))
    out, info = f.fix(words(*texts))
    return [w[4] for w in out], info


def test_clear_numbers_untouched():
    assert fixed(["spa"], None, "1.234,56", "245,60", "12.345,00")[0] == ["1.234,56", "245,60", "12.345,00"]


def test_misread_symbols_fixed_by_position():
    doc = ("1.234,56", "245,60", "12.345,00", "99,90", "1,234,56", "245.60")
    out, info = fixed(["spa"], None, *doc)
    assert out[4] == "1.234,56" and out[5] == "245,60" and len(info) == 2


def test_not_quantities_left_alone():
    texts = ("14.11.2026", "ABX-48213", "18:00", "912", "3.5mm")
    assert fixed(["spa"], None, *texts)[0] == list(texts)


def test_single_separator_three_digits_is_flagged():
    out, info = fixed(["spa"], None, "1.234")
    assert out == ["1.234"] and list(info.values())[0][0] == "flag"


def test_affixes_kept():
    assert fixed(["spa"], ("1.234,56", "2.345,67"), "€1,234,56")[0] == ["€1.234,56"]


def test_english_document():
    assert fixed(["eng"], None, "1,234.56", "99.90", "1.234.56")[0] == ["1,234.56", "99.90", "1,234.56"]


def test_no_convention_no_change():
    assert fixed([], None, "1,234,56", "245.60")[0] == ["1,234,56", "245.60"]


if __name__ == "__main__":
    n = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            n += 1
    print(f"{n} pruebas ok")
