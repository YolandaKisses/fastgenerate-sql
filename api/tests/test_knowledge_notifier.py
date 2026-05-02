import threading

from app.services.knowledge_service import _TaskNotifier


def test_task_notifier_wakes_multiple_subscribers_without_lost_update():
    notifier = _TaskNotifier()
    task_id = 42
    results: list[int] = []

    def wait_for_update() -> None:
        results.append(notifier.wait(task_id, last_version=0, timeout=0.5))

    first = threading.Thread(target=wait_for_update)
    second = threading.Thread(target=wait_for_update)
    first.start()
    second.start()

    notifier.notify(task_id)
    first.join(timeout=1)
    second.join(timeout=1)

    assert sorted(results) == [1, 1]
