import pytest

from scripts.accuracy import edit_distance, error_metrics, normalized


@pytest.mark.parametrize("reference,hypothesis,distance", [("", "", 0), ("", "x", 1), ("مرحبا", "مرحبا", 0),
                                                          ("kitten", "sitting", 3), (["a", "b"], ["b"], 1)])
def test_transcription_edit_distance(reference, hypothesis, distance):
    assert edit_distance(reference, hypothesis) == distance


def test_accuracy_normalization_does_not_hide_arabic_errors():
    assert normalized("أهلا\nبكم") == normalized("ا\u0654هلا  بكم")
    assert error_metrics("مرحبا", "مرحبا")['cer'] == 0
    assert error_metrics("مَرْحَبًا", "مرحبا")['character_errors'] > 0
    assert error_metrics("١٢٣", "123")['cer'] == 1
    assert error_metrics("Hello!", "Hello")['character_errors'] == 1
    assert error_metrics("x", "long hallucinated text")['cer'] > 1
