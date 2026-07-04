"""django-rq backend adapter.

Install: uv add django-rq rq
Set: TASK_BACKEND=django_rq

Simple Redis Queue wrapper for Django with a built-in dashboard.

Worker: python manage.py rqworker default
Dashboard: Add to urls.py:  path("django-rq/", include("django_rq.urls"))
"""

import functools


def rq_task(func):
    """Wrap a function as an RQ job.

    The decorated function can be called normally (sync) or via
    .delay() to enqueue it on the default RQ queue.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    def delay(*args, **kwargs):
        import django_rq

        queue = django_rq.get_queue("default")
        return queue.enqueue(func, *args, **kwargs)

    wrapper.delay = delay
    return wrapper
