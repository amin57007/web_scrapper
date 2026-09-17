"""Typed errors for scraping and KiCad import."""

from __future__ import annotations


class UlscrapeError(Exception):
    """Base error for the Ultra Librarian → KiCad pipeline."""


class UrlParseError(UlscrapeError):
    """The given text is not a recognized Ultra Librarian part URL."""


class DetailsParseError(UlscrapeError):
    """The details HTML did not contain the expected part fields."""


class AuthError(UlscrapeError):
    """Login or session cookies are missing or rejected."""


class ExportError(UlscrapeError):
    """Queueing or downloading a CAD package failed."""


class CaptchaError(UlscrapeError):
    """Google reCAPTCHA on the export form could not be completed."""


class ArchiveError(UlscrapeError):
    """The zip is not a usable Ultra Librarian / KiCad export."""
