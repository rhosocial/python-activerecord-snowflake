# Changelog Fragments

We use [Towncrier](https://towncrier.readthedocs.io/) to manage our changelog.
Each significant change should have a corresponding fragment file.

## Creating a Fragment

1. **Filename**: `{issue_number}.{type}.md`
   - Example: `123.added.md`

2. **Types**:
   - `security` - Security fixes (always significant)
   - `removed` - Removed features (breaking changes)
   - `deprecated` - Deprecation notices
   - `added` - New features
   - `changed` - Behavior changes
   - `fixed` - Bug fixes
   - `performance` - Performance improvements
   - `docs` - Documentation (significant changes only)
   - `internal` - Internal changes (optional)

3. **Content**:
   - Write in past tense
   - Be specific but concise
   - Focus on user impact
   - One change per fragment

## Commands

```bash
# Preview changelog
towncrier build --draft --version X.Y.Z

# Build changelog (removes fragments)
towncrier build --version X.Y.Z --yes
```
