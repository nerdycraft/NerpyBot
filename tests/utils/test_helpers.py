from utils.helpers import parse_id


def test_parse_id_from_int():
    assert parse_id(283746501234567890) == 283746501234567890


def test_parse_id_from_string():
    assert parse_id("283746501234567890") == 283746501234567890
