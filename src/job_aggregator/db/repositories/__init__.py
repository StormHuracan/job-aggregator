from job_aggregator.db.repositories.saved_search import SavedSearchRepository
from job_aggregator.db.repositories.vacancy import (
    VacancyRepository,
    VacancyUpsertResult,
)

__all__ = [
    "SavedSearchRepository",
    "VacancyRepository",
    "VacancyUpsertResult",
]
