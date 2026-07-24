# Pull Request

## Description

<!-- Provide a clear and concise description of what this PR does. -->
<!-- Include the motivation and context for the changes. -->

### What changed?


### Why was this change needed?


## Type of Change

<!-- Mark the relevant option with an "x" -->

- [ ] **Feature** - New functionality or capability
- [ ] **Bug Fix** - Fixes an issue without changing existing functionality
- [ ] **Refactor** - Code changes that neither fix a bug nor add a feature
- [ ] **Performance** - Improves performance without changing functionality
- [ ] **Documentation** - Updates to documentation only
- [ ] **Tests** - Adding or updating tests only
- [ ] **CI/CD** - Changes to CI/CD configuration
- [ ] **Dependencies** - Dependency updates or changes
- [ ] **Breaking Change** - Changes that break backward compatibility

## Related Issues

<!-- Link any related issues using GitHub keywords -->
<!-- Examples: "Fixes #123", "Closes #456", "Related to #789" -->

-

## Testing Done

<!-- Describe the testing you have performed -->
<!-- Include relevant details about your test environment -->

### Test Commands Run

```bash
# Example:
# make test
# make lint
```

### Test Coverage

<!-- If applicable, include coverage changes -->

- [ ] All existing tests pass
- [ ] New tests added for new functionality
- [ ] Edge cases considered and tested

### Manual Testing

<!-- Describe any manual testing performed -->


## Screenshots / Recordings

<!-- If this PR includes UI changes, add screenshots or recordings -->
<!-- Delete this section if not applicable -->

| Before | After |
|--------|-------|
|        |       |

## API Changes

<!-- If this PR changes the API, document the changes -->
<!-- Delete this section if not applicable -->

### New Endpoints


### Modified Endpoints


### Removed Endpoints


## Database Changes

<!-- If this PR includes database migrations -->
<!-- Delete this section if not applicable -->

- [ ] New migrations included
- [ ] Migrations are reversible
- [ ] Data migration tested (if applicable)

## Checklist

<!-- Ensure all items are completed before requesting review -->

### Code Quality
- [ ] Code follows the project's style guidelines (ruff, pre-commit)
- [ ] Self-review of code completed
- [ ] Code is well-commented, especially in complex areas
- [ ] No unnecessary debugging code or print statements

### Testing
- [ ] Tests pass locally (`make test`)
- [ ] Linting passes (`make lint`)
- [ ] Gauntlet passes (`make gauntlet-quick`)
- [ ] Type checking passes (if applicable)

### Documentation
- [ ] Documentation updated (if needed)
- [ ] API documentation updated (if API changes)
- [ ] CHANGELOG updated (for significant changes)

### Security
- [ ] No sensitive data (secrets, credentials) committed
- [ ] Security implications considered
- [ ] Input validation added where needed

### Deployment
- [ ] Environment variables documented (if new ones added)
- [ ] Migration steps documented (if needed)
- [ ] Backward compatible (or breaking changes documented)

## Additional Notes

<!-- Any additional information reviewers should know -->


---

<!--
Reviewer Guidelines:
- Check code quality and adherence to project standards
- Verify tests are comprehensive and pass
- Review for security implications
- Ensure documentation is updated
- Test locally if possible
-->
