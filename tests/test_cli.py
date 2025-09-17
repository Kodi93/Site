"""Tests for the command-line interface helpers."""

from __future__ import annotations

from giftgrab import cli


def test_build_parser_defaults_to_generate(monkeypatch):
    """The parser should default to the generate command when none is provided."""

    monkeypatch.delenv("GIFTGRAB_DEFAULT_COMMAND", raising=False)
    parser = cli.build_parser()

    args = parser.parse_args([])

    assert args.command == "generate"


def test_build_parser_allows_env_override(monkeypatch):
    """An environment variable can set the default command."""

    monkeypatch.setenv("GIFTGRAB_DEFAULT_COMMAND", "update")
    parser = cli.build_parser()

    args = parser.parse_args([])

    assert args.command == "update"


def test_build_parser_invalid_env_falls_back_to_generate(monkeypatch):
    """Unexpected environment overrides should not break the parser."""

    monkeypatch.setenv("GIFTGRAB_DEFAULT_COMMAND", "invalid")
    parser = cli.build_parser()

    args = parser.parse_args([])

    assert args.command == "generate"
