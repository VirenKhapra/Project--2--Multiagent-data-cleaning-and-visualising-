import pytest

from app.services.file_validation import detect_file_signature, validate_file_signature


def test_detect_pdf_signature():
    contents = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    detected = detect_file_signature(contents)
    assert ".pdf" in detected


def test_validate_json_signature():
    contents = b'{"name": "Manas", "amount": 100}'
    validate_file_signature(extension=".json", contents=contents)


def test_validate_csv_signature():
    contents = b"name,amount\nManas,100\nAsha,200\n"
    validate_file_signature(extension=".csv", contents=contents)


def test_reject_mismatched_signature():
    contents = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    with pytest.raises(ValueError):
        validate_file_signature(extension=".csv", contents=contents)


def test_validate_plain_text_signature():
    contents = b"This is a plain text note.\nSecond line.\n"
    validate_file_signature(extension=".txt", contents=contents)
