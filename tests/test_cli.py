"""Tests for the command-line interface helpers."""

from __future__ import annotations

import pytest

from giftgrab import cli


def test_build_parser_leaves_command_unset_until_runtime(monkeypatch):
    """The parser should defer command selection until runtime."""

    monkeypatch.delenv("GIFTGRAB_DEFAULT_COMMAND", raising=False)
    parser = cli.build_parser()

    args = parser.parse_args([])

    assert args.command is None
    assert getattr(args, "_default_command") == "generate"


def test_build_parser_allows_env_override(monkeypatch):
    """An environment variable can set the default command."""

    monkeypatch.setenv("GIFTGRAB_DEFAULT_COMMAND", "update")
    parser = cli.build_parser()

    args = parser.parse_args([])

    assert args.command is None
    assert getattr(args, "_default_command") == "update"


def test_build_parser_invalid_env_falls_back_to_generate(monkeypatch):
    """Unexpected environment overrides should not break the parser."""

    monkeypatch.setenv("GIFTGRAB_DEFAULT_COMMAND", "invalid")
    parser = cli.build_parser()

    args = parser.parse_args([])

    assert args.command is None
    assert getattr(args, "_default_command") == "generate"


def test_main_without_command_fetches_when_repository_empty(monkeypatch):
    """On first run the CLI should automatically fetch products."""

    monkeypatch.delenv("GIFTGRAB_DEFAULT_COMMAND", raising=False)
    static_adapter = object()
    captured: dict[str, dict[str, object]] = {}

    class DummyRepository:
        def __init__(self, data_file):
            self.data_file = data_file

        def load_products(self):
            return []

    class DummyGenerator:
        def __init__(self, settings, output_dir):
            self.settings = settings
            self.output_dir = output_dir

        def build(self, categories, products, *, articles=None):  # pragma: no cover - stub
            return None

    class DummyArticleRepository:
        def __init__(self, path):
            self.path = path

        def list_published(self):  # pragma: no cover - stub
            return []

    class DummyPipeline:
        def __init__(
            self,
            *,
            repository,
            generator,
            categories,
            credentials,
            retailers,
            article_repository,
        ):
            captured["init"] = {
                "repository": repository,
                "generator": generator,
                "categories": categories,
                "credentials": credentials,
                "retailers": retailers,
                "article_repository": article_repository,
            }

        def run(self, *, item_count, regenerate_only):
            captured["run"] = {
                "item_count": item_count,
                "regenerate_only": regenerate_only,
            }

    monkeypatch.setattr(cli, "ProductRepository", DummyRepository)
    monkeypatch.setattr(cli, "SiteGenerator", DummyGenerator)
    monkeypatch.setattr(cli, "GiftPipeline", DummyPipeline)
    monkeypatch.setattr(cli, "ArticleRepository", DummyArticleRepository)
    monkeypatch.setattr(cli, "load_credentials", lambda: None)
    monkeypatch.setattr(cli, "load_static_retailers", lambda: [static_adapter])
    monkeypatch.setattr(cli, "ensure_directories", lambda: None)

    cli.main([])

    assert captured["run"]["regenerate_only"] is False
    assert captured["run"]["item_count"] == 6
    assert captured["init"]["retailers"] == [static_adapter]
    assert captured["init"]["credentials"] is None


def test_main_without_command_uses_default_when_products_exist(monkeypatch):
    """With stored data the default command should be used."""

    monkeypatch.delenv("GIFTGRAB_DEFAULT_COMMAND", raising=False)
    static_adapter = object()
    captured: dict[str, dict[str, object]] = {}

    class DummyRepository:
        def __init__(self, data_file):
            self.data_file = data_file

        def load_products(self):
            return ["stored"]

    class DummyGenerator:
        def __init__(self, settings, output_dir):
            self.settings = settings
            self.output_dir = output_dir

        def build(self, categories, products, *, articles=None):  # pragma: no cover - stub
            return None

    class DummyArticleRepository:
        def __init__(self, path):
            self.path = path

        def list_published(self):  # pragma: no cover - stub
            return []

    class DummyPipeline:
        def __init__(
            self,
            *,
            repository,
            generator,
            categories,
            credentials,
            retailers,
            article_repository,
        ):
            captured["init"] = {
                "repository": repository,
                "generator": generator,
                "categories": categories,
                "credentials": credentials,
                "retailers": retailers,
                "article_repository": article_repository,
            }

        def run(self, *, item_count, regenerate_only):
            captured["run"] = {
                "item_count": item_count,
                "regenerate_only": regenerate_only,
            }

    def fail_credentials():
        raise AssertionError("Credentials should not be loaded for generate runs")

    monkeypatch.setattr(cli, "ProductRepository", DummyRepository)
    monkeypatch.setattr(cli, "SiteGenerator", DummyGenerator)
    monkeypatch.setattr(cli, "GiftPipeline", DummyPipeline)
    monkeypatch.setattr(cli, "ArticleRepository", DummyArticleRepository)
    monkeypatch.setattr(cli, "load_credentials", fail_credentials)
    monkeypatch.setattr(cli, "load_static_retailers", lambda: [static_adapter])
    monkeypatch.setattr(cli, "ensure_directories", lambda: None)

    cli.main([])

    assert captured["run"]["regenerate_only"] is True
    assert captured["init"]["retailers"] == [static_adapter]
    assert captured["init"]["credentials"] is None


def test_main_generate_without_products_errors(monkeypatch):
    """Explicitly requesting generate without data should fail clearly."""

    monkeypatch.delenv("GIFTGRAB_DEFAULT_COMMAND", raising=False)

    class DummyRepository:
        def __init__(self, data_file):
            self.data_file = data_file

        def load_products(self):
            return []

    class DummyGenerator:
        def __init__(self, settings, output_dir):
            self.settings = settings
            self.output_dir = output_dir

    monkeypatch.setattr(cli, "ProductRepository", DummyRepository)
    monkeypatch.setattr(cli, "SiteGenerator", DummyGenerator)
    monkeypatch.setattr(cli, "ensure_directories", lambda: None)

    parser = cli.build_parser()
    captured: dict[str, str] = {}

    def fake_error(message: str) -> None:
        captured["message"] = message
        raise SystemExit(2)

    monkeypatch.setattr(parser, "error", fake_error)
    monkeypatch.setattr(cli, "build_parser", lambda: parser)

    with pytest.raises(SystemExit) as excinfo:
        cli.main(["generate"])

    assert excinfo.value.code == 2
    assert "Run 'update'" in captured["message"]
