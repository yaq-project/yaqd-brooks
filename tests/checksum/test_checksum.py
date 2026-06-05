import pathlib
from yaqd_brooks import _brooks_mfc_025x

__here__ = pathlib.Path(__file__).parent


def test_valid_responses():
    with open(__here__ / "valid_responses.txt", "r") as f:
        for line in f:
            byt = line.encode()
            assert _brooks_mfc_025x.is_valid_checksum(byt)


def test_invalid_responses():
    with open(__here__ / "invalid_responses.txt", "r") as f:
        for line in f:
            byt = line.encode()
            assert not _brooks_mfc_025x.is_valid_checksum(byt)


if __name__ == "__main__":
    test_valid_responses()
    test_invalid_responses()
