import pytest

from scripts.smoke_binary import assert_sample_text, sample_languages


@pytest.mark.parametrize("languages,text", [
    ("eng", "Turn your screenshots into something useful."),
    ("ara", "مرحبا بالعالم"),
    ("ara+eng", "مرحبا بالعالم\nTurn your screenshots into something useful."),
])
def test_native_sample_checks_each_declared_language(languages, text):
    assert_sample_text(text, languages)
    assert_sample_text(text, languages, vision=True)


@pytest.mark.parametrize("languages,text", [
    ("ara", "screenshots"), ("eng", "مرحبا بالعالم"),
    ("ara+eng", "screenshots"), ("ara+eng", "مرحبا بالعالم"),
])
def test_bilingual_model_cannot_pass_with_only_one_language(languages, text):
    with pytest.raises(AssertionError):
        assert_sample_text(text, languages, vision=True)


def test_vlm_presence_check_allows_optional_marks_without_changing_corpus_accuracy():
    value = "مَرْحَـبًا بِالْعَالَم"
    assert_sample_text(value, "ara", vision=True)
    with pytest.raises(AssertionError):
        assert_sample_text(value, "ara")
    with pytest.raises(ValueError):
        assert_sample_text(value, "invalid", vision=True)


def test_vlm_capability_probe_is_separate_from_per_character_accuracy():
    assert_sample_text("اللغة العربية واللغة الإنجليزية\nscreenshots", "ara+eng", vision=True)
    with pytest.raises(AssertionError):
        assert_sample_text("مربح بالعالم\nscreenshots", "ara+eng", vision=True)


@pytest.mark.parametrize("method,key,default", [("vision", "embedded_models", "default_model"),
                                               ("neural", "embedded_neural", "default_neural")])
def test_embedded_sample_capability_follows_selected_pack_instead_of_another_model(method, key, default):
    profile = {key: [{"id": "english", "languages": "eng"}, {"id": "bilingual", "languages": "ara+eng"}], default: "english"}
    assert sample_languages(profile, method, "") == "eng"
    assert sample_languages(profile, method, "bilingual") == "ara+eng"
    with pytest.raises(ValueError):
        sample_languages(profile, method, "missing")
    profile[key][1]["languages"] = "unsupported"
    with pytest.raises(ValueError):
        sample_languages(profile, method, "bilingual")


def test_classical_sample_remains_bilingual():
    assert sample_languages({}, "tesseract-fast", "") == "ara+eng"
