from job_aggregator.integrations.hh.dto import (
    HHVacancyPage,
    HHVacancySearchParams,
)


class FakeHHClient:
    def __init__(
        self,
        *,
        pages: dict[int, HHVacancyPage],
        error: Exception | None = None,
    ) -> None:
        self.pages = pages
        self.error = error
        self.calls: list[HHVacancySearchParams] = []

    async def search_vacancies(
        self,
        params: HHVacancySearchParams,
    ) -> HHVacancyPage:
        self.calls.append(params)

        if self.error is not None:
            raise self.error

        if params.page not in self.pages:
            raise ValueError(f"Нет страницы с номером {params.page}")

        return self.pages[params.page]
