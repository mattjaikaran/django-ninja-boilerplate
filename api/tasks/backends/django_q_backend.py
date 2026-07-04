"""django-q2 backend adapter.

Install: uv add django-q2
Set: TASK_BACKEND=django_q

django-q2 uses multiprocessing worker pools with Django admin integration.

Worker: python manage.py qcluster
"""

import functools


def django_q_task(func):
    """Wrap a function as a django-q async_task callable.

    The decorated function can be called normally (sync) or via
    .delay() to dispatch it to the django-q cluster.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    def delay(*args, **kwargs):
        from django_q.tasks import async_task

        return async_task(func, *args, **kwargs)

    wrapper.delay = delay
    return wrapper
