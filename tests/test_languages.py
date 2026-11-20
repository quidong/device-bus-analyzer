"""All five UI languages: same keys, same placeholders, catalogue complete, switcher and detection work."""
import pytest
from test_companion import login  # noqa: F401
from test_web import app, client  # noqa: F401

from device_bus_analyzer import catalog, i18n


def test_all_languages_have_the_same_keys_and_placeholders():
    assert set(i18n.LANGS) == set(i18n.STR)
    for lang in i18n.LANGS:
        assert set(i18n.STR[lang]) == set(i18n.STR["en"]), lang
        for k, v in i18n.STR["en"].items():
            assert v.count("{}") == i18n.STR[lang][k].count("{}"), (lang, k)
            assert i18n.STR[lang][k].strip(), (lang, k)


def test_catalogue_is_complete_in_every_language():
    assert catalog.validate_catalog() == []
    for lang in i18n.LANGS:
        c = catalog.controls("dishwasher", lang)
        assert c["events"] and all(e["label"] for e in c["events"]) and all(s["text"] for g in c["guided"] for s in g["steps"])
        assert catalog.firmware_profile("bshdbus", lang)["note"]
    assert catalog.controls("dryer", "it")["guided"][1]["label"] != catalog.controls("dryer", "en")["guided"][1]["label"]


@pytest.mark.parametrize("header,expected", [("fr-FR,fr;q=0.9,en;q=0.8", "fr"), ("es-MX", "es"), ("it", "it"), ("de-DE", "de"),
                                             ("en-US", "en"), ("pt-BR", "en"), (None, "en"), ("", "en")])
def test_language_detection_from_accept_language(header, expected):
    assert i18n.pick(header, None, None) == expected


def test_query_and_cookie_win_and_unknown_values_are_ignored():
    assert i18n.pick("de", None, "it") == "it" and i18n.pick("de", "fr", None) == "fr" and i18n.pick("de", None, "xx") == "de"


@pytest.mark.parametrize("lang,word", [("es", "Tramas"), ("fr", "Trames"), ("it", "Frame")])
def test_pages_render_in_the_new_languages_and_the_switcher_lists_all(client, lang, word):
    login(client)
    html = client.get("/devices", params={"lang": lang}).text
    assert i18n.STR[lang]["devices_title"] in html and i18n.STR[lang]["help_link"] in html
    for name in ("Deutsch", "English", "Español", "Français", "Italiano"):
        assert f">{name}</option>" in html
    assert f'<option value="{lang}" selected>' in html
    assert word in client.get("/s/dw/frames", params={"lang": lang}).text
    assert i18n.STR[lang]["cp_title"] in client.get("/s/dw/companion", params={"lang": lang}).text
