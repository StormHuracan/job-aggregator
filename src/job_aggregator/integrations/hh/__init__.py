"""Изолированный слой интеграции с HH.ru."""

from job_aggregator.integrations.hh.client import HHClient
from job_aggregator.integrations.hh.oauth import HHOAuthClient

__all__ = ["HHClient", "HHOAuthClient"]
