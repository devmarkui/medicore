import json
import os

from flask import g, request


SUPPORTED_LANGS = {"en", "si", "ta"}


def load_translations(lang: str) -> dict:
    base_dir = os.path.join(os.path.dirname(__file__), "i18n")
    path = os.path.join(base_dir, f"{lang}.json")
    if not os.path.exists(path):
        path = os.path.join(base_dir, "en.json")
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def init_i18n(app):
    @app.before_request
    def _set_language():
        lang = request.args.get("lang", "en")
        if lang not in SUPPORTED_LANGS:
            lang = "en"
        g.current_lang = lang
        g.translations = load_translations(lang)

    @app.context_processor
    def _inject_translations():
        return {
            "t": getattr(g, "translations", {}),
            "current_lang": getattr(g, "current_lang", "en"),
        }
