from job_aggregator.db.repositories.vacancy import VacancyUpsertResult
from job_aggregator.schemas.vacancy import VacancyData


class FakeVacancyRepository:
    """Возвращает заданные исходы upsert по порядку, записывая входные данные."""

    def __init__(self, outcomes: list[VacancyUpsertResult | BaseException]) -> None:
        self.outcomes = iter(outcomes)
        self.calls: list[VacancyData] = []

    async def upsert(self, vacancy: VacancyData) -> VacancyUpsertResult:
        self.calls.append(vacancy)
        outcome = next(self.outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome
