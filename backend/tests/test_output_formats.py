from app.constants import DEFAULT_OUTPUT_FORMAT_OPTIONS


def test_supported_output_formats_include_recoverable_text_and_json():
    assert DEFAULT_OUTPUT_FORMAT_OPTIONS == [
        "XLSX",
        "PDF",
        "PNG",
        "CSV",
        "JSON",
        "TXT",
    ]
