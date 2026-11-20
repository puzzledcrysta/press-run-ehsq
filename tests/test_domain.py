from decimal import Decimal
import pytest
from app.errors import DataError
from app.modules.domain.rule import evaluate


def test_two_losses(cases):
    actual, evidence = evaluate(cases['two_losses'])
    assert actual == Decimal('7706')
    assert evidence and all(len(row)==3 for row in evidence)


def test_all_setup(cases):
    actual, evidence = evaluate(cases['all_setup'])
    assert actual == Decimal('0')


def test_whole_bundle(cases):
    actual, evidence = evaluate(cases['whole_bundle'])
    assert actual == Decimal('1000')


def test_tail(cases):
    actual, evidence = evaluate(cases['tail'])
    assert actual == Decimal('77')


def test_too_much_setup(cases):
    with pytest.raises(DataError) as error:
        evaluate(cases['too_much_setup'])
    assert error.value.code in {'BUSINESS','NUMBER','RANGE','TIMESTAMP'}


def test_too_much_die(cases):
    with pytest.raises(DataError) as error:
        evaluate(cases['too_much_die'])
    assert error.value.code in {'BUSINESS','NUMBER','RANGE','TIMESTAMP'}


def test_bad_bundle(cases):
    with pytest.raises(DataError) as error:
        evaluate(cases['bad_bundle'])
    assert error.value.code in {'BUSINESS','NUMBER','RANGE','TIMESTAMP'}

