from job_aggregator.db.repositories.saved_search import SavedSearchRepository
from job_aggregator.db.repositories.vacancy import (
    VacancyRepository,
    VacancyUpsertResult,
)

__all__ = [
    "HHAccountRepository",
    "SavedSearchRepository",
    "VacancyRepository",
    "VacancyUpsertResult",
]
from job_aggregator.db.repositories.hh_account import HHAccountRepository
