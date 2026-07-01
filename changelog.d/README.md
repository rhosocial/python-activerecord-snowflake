# Changelog Fragments

We use Towncrier to manage our changelog. Each significant change should have a corresponding fragment file.

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

## Fragment Lifecycle

- **Created**: When feature/fix branch is created
- **Merged**: Fragment merges with the code
- **Compiled**: During final release (not pre-releases)
- **Deleted**: Automatically removed after compilation
- **Abandoned**: Manually deleted if feature is abandoned

## Good Examples

```markdown
<!-- 123.added.md -->
Added support for Snowflake-specific VARIANT and ARRAY types, enabling semi-structured data handling.
```

```markdown
<!-- 456.fixed.md -->
Fixed time travel query formatting when using AT() with TIMESTAMP expressions.
```

```markdown
<!-- 789.security.md -->
**SECURITY**: Fixed SQL injection vulnerability in stage name handling during COPY INTO operations.
```

## When to Skip

- Internal refactoring (no behavior change)
- Trivial fixes (typos in comments)
- Work-in-progress (fragment in final PR)

## If Feature is Abandoned

Simply delete the fragment file:

```bash
rm changelog.d/123.added.md
```

## Commands

```bash
# Preview changelog
towncrier build --draft --version X.Y.Z

# Build changelog (removes fragments)
towncrier build --version X.Y.Z --yes
```

## Fragment Types in Detail

### Security (`security`)
Use for any security vulnerability fixes. Always include CVE number if available.

### Removed (`removed`)
Use for removed features or APIs (breaking changes). Explain what was removed and what to use instead.

### Deprecated (`deprecated`)
Use for deprecation notices. Include timeline for removal and recommended alternative.

### Added (`added`)
Use for new features. Describe what users can now do that they couldn't before.

### Changed (`changed`)
Use for changes to existing functionality (non-breaking). Explain what changed and why.

### Fixed (`fixed`)
Use for bug fixes. Describe the problem that was fixed.

### Performance (`performance`)
Use for performance improvements. Include metrics if possible.

### Documentation (`docs`)
Use only for significant documentation changes (new guides, major reorganization).

### Internal (`internal`)
Optional. Use for internal changes that don't affect users directly.

## Multiple Issues

If a change affects multiple issues, use `+` in the filename:

```bash
# Change affects issues #123 and #456
123+456.fixed.md
```

## Review Checklist

Before committing your fragment:

- [ ] Filename follows `{issue}.{type}.md` format
- [ ] Content is in past tense
- [ ] Describes user impact, not implementation
- [ ] One logical change per fragment
- [ ] Appropriate type selected
- [ ] Security issues marked with **SECURITY** prefix
- [ ] Breaking changes marked with **BREAKING** prefix
