from job_aggregator.db.models.user import User
from job_aggregator.db.repositories.collection_progress import (
    CollectionProgressRepository,
    collection_search_key,
)


async def test_progress_is_persistent_and_isolated(sqlite_session):
    sqlite_session.add_all(
        [
            User(id=1, hh_user_id="one", display_name="Один"),
            User(id=2, hh_user_id="two", display_name="Два"),
        ]
    )
    await sqlite_session.commit()
    repo = CollectionProgressRepository(sqlite_session)
    key = collection_search_key(" python ", "")
    assert key == collection_search_key("python", None)
    assert key != collection_search_key("python", "1")
    assert key != collection_search_key("Python", None)
    first = await repo.get_for_update(1, key)
    assert (first.next_page, first.exhausted) == (0, False)
    first.next_page = 3
    first.exhausted = True
    await sqlite_session.commit()
    sqlite_session.expunge_all()

    restored = await repo.get_for_update(1, key)
    assert (restored.next_page, restored.exhausted) == (3, True)
    other = await repo.get_for_update(2, key)
    region = await repo.get_for_update(1, collection_search_key("python", "1"))
    assert (other.next_page, region.next_page) == (0, 0)
    await sqlite_session.commit()

    restored.next_page = 9
    await sqlite_session.flush()
    await sqlite_session.rollback()
    restored = await repo.get_for_update(1, key)
    assert restored.next_page == 3
