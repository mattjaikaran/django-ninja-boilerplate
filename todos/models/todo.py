from django.db import models
from django.conf import settings
from core.models import AbstractBaseModel


class Todo(AbstractBaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="todos"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    completed = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Todo"
        verbose_name_plural = "Todos"
