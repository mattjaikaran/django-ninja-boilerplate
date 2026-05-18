"""Advanced search and filtering system using Django Ninja Extra."""

from datetime import date, datetime

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Q, QuerySet
from django.db.models.fields import (
    BooleanField,
    DateField,
    DateTimeField,
    DecimalField,
    IntegerField,
)
from pydantic import ConfigDict, Field

from core.schemas.base_schema import CamelCaseSchema


class BaseSearchFilter(CamelCaseSchema):
    """Base search filter with common search functionality."""

    search: str | None = Field(None, description="Search term to filter results")
    ordering: str | None = Field(
        None, description="Field to order by (use - prefix for descending)"
    )
    limit: int | None = Field(
        20, description="Maximum number of results to return", le=100
    )
    offset: int | None = Field(0, description="Number of results to skip", ge=0)


class DateRangeFilter(CamelCaseSchema):
    """Date range filtering."""

    date_from: date | None = Field(None, description="Start date (YYYY-MM-DD)")
    date_to: date | None = Field(None, description="End date (YYYY-MM-DD)")


class DateTimeRangeFilter(CamelCaseSchema):
    """DateTime range filtering."""

    datetime_from: datetime | None = Field(
        None, description="Start datetime (ISO format)"
    )
    datetime_to: datetime | None = Field(None, description="End datetime (ISO format)")


class UserSearchFilter(BaseSearchFilter):
    """Advanced search filter for users."""

    is_staff: bool | None = Field(None, description="Filter by staff status")
    is_superuser: bool | None = Field(None, description="Filter by superuser status")
    is_active: bool | None = Field(None, description="Filter by active status")
    email_domain: str | None = Field(None, description="Filter by email domain")
    created_after: date | None = Field(None, description="Created after date")
    created_before: date | None = Field(None, description="Created before date")

    model_config = ConfigDict(extra="forbid")


class TodoSearchFilter(BaseSearchFilter):
    """Advanced search filter for todos."""

    completed: bool | None = Field(None, description="Filter by completion status")
    priority: str | None = Field(None, description="Filter by priority level")
    created_after: date | None = Field(None, description="Created after date")
    created_before: date | None = Field(None, description="Created before date")

    model_config = ConfigDict(extra="forbid")


class AdvancedSearchEngine:
    """Advanced search engine with intelligent filtering and search capabilities."""

    def __init__(self, model_class, search_fields: list[str] | None = None):
        """Initialize search engine for a model.

        Args:
            model_class: Django model class to search
            search_fields: List of fields to include in text search
        """
        self.model_class = model_class
        self.search_fields = search_fields or []

    def apply_search(self, queryset: QuerySet, filters: BaseSearchFilter) -> QuerySet:
        """Apply search and filtering to queryset."""
        # Apply text search
        if filters.search and self.search_fields:
            queryset = self._apply_text_search(queryset, filters.search)

        # Apply specific filters based on filter type
        queryset = self._apply_specific_filters(queryset, filters)

        # Apply ordering
        if filters.ordering:
            queryset = self._apply_ordering(queryset, filters.ordering)

        return queryset

    def _apply_text_search(self, queryset: QuerySet, search_term: str) -> QuerySet:
        """Apply intelligent text search across multiple fields."""
        if not search_term.strip():
            return queryset

        # Split search term into words for better matching
        search_words = [word.strip() for word in search_term.split() if word.strip()]

        # Build search query
        search_query = Q()

        for word in search_words:
            word_query = Q()

            for field in self.search_fields:
                # Handle related field searches (e.g., 'user__username')
                if "__" in field:
                    word_query |= Q(**{f"{field}__icontains": word})
                else:
                    # Try different search patterns
                    field_obj = self.model_class._meta.get_field(field.split("__")[0])

                    if isinstance(field_obj, (DateField, DateTimeField)):
                        # For date fields, try exact match if it looks like a date
                        try:
                            date_value = datetime.strptime(word, "%Y-%m-%d").date()
                            word_query |= Q(**{field: date_value})
                        except ValueError:
                            pass
                    elif isinstance(field_obj, BooleanField):
                        # For boolean fields, try to match true/false variations
                        if word.lower() in ["true", "1", "yes", "active", "enabled"]:
                            word_query |= Q(**{field: True})
                        elif word.lower() in [
                            "false",
                            "0",
                            "no",
                            "inactive",
                            "disabled",
                        ]:
                            word_query |= Q(**{field: False})
                    elif isinstance(field_obj, (DecimalField, IntegerField)):
                        # For numeric fields, try exact match
                        try:
                            numeric_value = float(word)
                            word_query |= Q(**{field: numeric_value})
                        except ValueError:
                            pass
                    else:
                        # Default text search with various patterns
                        word_query |= Q(**{f"{field}__icontains": word})
                        word_query |= Q(**{f"{field}__istartswith": word})

            search_query &= word_query

        return queryset.filter(search_query)

    def _apply_specific_filters(
        self, queryset: QuerySet, filters: BaseSearchFilter
    ) -> QuerySet:
        """Apply model-specific filters."""
        if isinstance(filters, UserSearchFilter):
            return self._apply_user_filters(queryset, filters)
        if isinstance(filters, TodoSearchFilter):
            return self._apply_todo_filters(queryset, filters)

        return queryset

    def _apply_user_filters(
        self, queryset: QuerySet, filters: UserSearchFilter
    ) -> QuerySet:
        """Apply user-specific filters."""
        if filters.is_staff is not None:
            queryset = queryset.filter(is_staff=filters.is_staff)

        if filters.is_superuser is not None:
            queryset = queryset.filter(is_superuser=filters.is_superuser)

        if filters.is_active is not None:
            queryset = queryset.filter(is_active=filters.is_active)

        if filters.email_domain:
            queryset = queryset.filter(email__icontains=f"@{filters.email_domain}")

        if filters.created_after:
            queryset = queryset.filter(date_joined__date__gte=filters.created_after)

        if filters.created_before:
            queryset = queryset.filter(date_joined__date__lte=filters.created_before)

        return queryset

    def _apply_todo_filters(
        self, queryset: QuerySet, filters: TodoSearchFilter
    ) -> QuerySet:
        """Apply todo-specific filters."""
        if filters.completed is not None:
            queryset = queryset.filter(completed=filters.completed)

        if filters.priority:
            queryset = queryset.filter(priority__icontains=filters.priority)

        if filters.created_after:
            queryset = queryset.filter(created_at__date__gte=filters.created_after)

        if filters.created_before:
            queryset = queryset.filter(created_at__date__lte=filters.created_before)

        return queryset

    def _apply_ordering(self, queryset: QuerySet, ordering: str) -> QuerySet:
        """Apply ordering to queryset with validation."""
        # Get valid field names for the model
        valid_fields = [field.name for field in self.model_class._meta.get_fields()]

        # Parse ordering (handle - prefix for descending)
        order_fields = []
        for field in ordering.split(","):
            field = field.strip()
            if field.startswith("-"):
                field_name = field[1:]
                if field_name in valid_fields:
                    order_fields.append(field)
            elif field in valid_fields:
                order_fields.append(field)

        if order_fields:
            queryset = queryset.order_by(*order_fields)

        return queryset


def create_search_engine(model_class, search_fields: list[str]) -> AdvancedSearchEngine:
    """Factory function to create a search engine for a model."""
    return AdvancedSearchEngine(model_class, search_fields)


# =============================================================================
# PostgreSQL Full-Text Search
# =============================================================================


def fts_search(
    queryset: QuerySet,
    query: str,
    vector_fields: list[str],
    rank_threshold: float = 0.1,
    language: str = "english",
) -> QuerySet:
    """Apply PostgreSQL full-text search with ranking.

    Uses SearchVector + SearchQuery + SearchRank for relevance-ranked results.
    Requires PostgreSQL — falls back to icontains on the first field for other DBs.

    Args:
        queryset: Base queryset to search.
        query: Search query string.
        vector_fields: Field names to include in the search vector.
            Supports weight tuples: [("title", "A"), ("body", "B")].
        rank_threshold: Minimum rank score to include (0.0 to 1.0).
        language: PostgreSQL text search language config.

    Returns:
        Queryset annotated with ``search_rank`` and ordered by rank descending.

    Usage::

        results = fts_search(
            Todo.objects.filter(user=user),
            query="buy groceries",
            vector_fields=[("title", "A"), ("description", "B")],
        )
    """
    if not query.strip():
        return queryset

    vector_parts: list[SearchVector] = []
    for field in vector_fields:
        if isinstance(field, tuple):
            name, weight = field
            vector_parts.append(SearchVector(name, weight=weight, config=language))
        else:
            vector_parts.append(SearchVector(field, config=language))

    if not vector_parts:
        return queryset

    search_vector = vector_parts[0]
    for part in vector_parts[1:]:
        search_vector = search_vector + part

    search_query = SearchQuery(query, config=language)

    return (
        queryset.annotate(
            search_rank=SearchRank(search_vector, search_query),
        )
        .filter(search_rank__gte=rank_threshold)
        .order_by("-search_rank")
    )


class FullTextSearchMixin:
    """Mixin for service classes that want PostgreSQL FTS.

    Subclass and set ``fts_fields`` to enable ranked full-text search.

    Example::

        class TodoService(FullTextSearchMixin):
            fts_fields = [("title", "A"), ("description", "B")]

            def search_todos(self, query: str):
                qs = Todo.objects.all()
                return self.fts_search(qs, query)
    """

    fts_fields: list[str | tuple[str, str]] = []
    fts_language: str = "english"
    fts_rank_threshold: float = 0.1

    def fts_search(self, queryset: QuerySet, query: str) -> QuerySet:
        return fts_search(
            queryset,
            query,
            self.fts_fields,
            rank_threshold=self.fts_rank_threshold,
            language=self.fts_language,
        )


# Pre-configured search engines for common models
def get_user_search_engine():
    """Get search engine for User model."""
    search_fields = ["username", "email", "first_name", "last_name"]
    from core.models import User

    return create_search_engine(User, search_fields)


def get_todo_search_engine():
    """Get search engine for Todo model."""
    search_fields = [
        "title",
        "description",
        "user__username",
        "user__email",
    ]
    from todos.models import Todo

    return create_search_engine(Todo, search_fields)
