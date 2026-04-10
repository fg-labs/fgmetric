# CLAUDE.md

## Template Setup

**On first interaction in a new project:** Check if these sections still contain placeholder text:
- Project Overview (look for `[Add 2-3 sentences`)
- Key Concepts (look for `[Term]:`)
- Codebase Architecture (look for `[Add tree output`)

If any are unpopulated, prompt the user to fill them in before proceeding with other work. Walk through each section conversationally—ask about the project, then draft content for the user to approve.

Delete this section once setup is complete.

## How Claude Should Work

### Before Starting
- Confirm understanding of task scope before writing code
- For changes >400 lines or spanning multiple modules, propose an implementation plan first (see Planning Documents below)
- Identify which existing modules/patterns to follow
- Check for related issues/PRs with `gh issue list` or `gh pr list`

### During Development
- Commit at logical boundaries (see Commit Granularity below)
- When uncertain about a design choice, pause and ask rather than guess
- Note assumptions made and flag them for review

### Decision-Making
**Ask first:**
- Architectural changes or new patterns
- New dependencies
- Deviating from established patterns
- Changes to public APIs
- Performance vs. readability tradeoffs

**Decide and document:**
- Implementation details within established patterns
- Test organization and naming
- Internal/private naming choices
- Order of operations within a function

When uncertain, state your assumption explicitly: *"Assuming X—correct me if that's wrong."*

### When Claude Disagrees
- Explain the concern clearly with specifics
- Offer alternatives rather than just objecting
- For style preferences, defer to project conventions
- For correctness/safety issues, push back firmly but constructively

### Context Maintenance
- Reference specific file paths and function names, not vague descriptions
- When resuming work, summarize current state and next steps
- Proactively save plans and notes to `agent_notes/`

### Planning Documents
For changes >400 lines or spanning multiple modules, create a plan:

```markdown
# agent_notes/YYYY-MM-DD_brief-description.md

## Goal
[One sentence describing the end state]

## Approach
1. [First step]
2. [Second step]
...

## Files to Modify
- `src/module.py` — add/change X
- `tests/test_module.py` — add tests for X

## Open Questions
- [Anything requiring user input]

## Progress
- [ ] Step 1
- [ ] Step 2
```

---

## Project Overview

<!-- After creating a project from this template, populate this section. -->

[2-3 sentences: What does this toolkit do? What problems does it solve? Who uses it?]

### Key Concepts

<!-- List 5-10 domain terms that appear in code but may be unfamiliar.
     Delete this comment block after populating. -->

- **[Term]:** Brief definition (e.g., "BAM files: Binary alignment/map files containing sequencing read alignments")
- **[Term]:** Brief definition

### Codebase Architecture

<!-- Add `tree -L 2 -d` output or equivalent, annotated with module purposes.
     Update when adding top-level modules. Delete this comment block. -->

```
project/
├── src/
├── tests/
└── ...
```

---

## Core Principles

**Priority order:** Correctness → Readability → Simplicity → Performance

1. **Correctness:** Structure code to be testable; isolate complex logic for unit testing.
2. **Readability:** If you'd change it on a rewrite, refactor now.
3. **Simplicity:** Prefer recognizable patterns. Don't introduce new patterns without discussion.
4. **Performance:** Correct implementation first. Profile before optimizing (see Performance section).

---

## Development Commands

```bash
# Run all checks (lint, type-check, test)
uv run poe fix-and-check-all

# Individual commands
uv run poe check-tests    # Run tests
uv run poe check-lints    # Lint only
uv run poe check-typing   # Type-check only

# Run specific test
uv run pytest tests/test_example.py::test_name -v

# GitHub CLI
gh issue list                    # View open issues
gh pr list                       # View open PRs
gh pr view 123                   # View specific PR
```

See `CONTRIBUTING.md` for full task list and environment setup.

---

## Git Workflow

### Commit Granularity

Commit after completing one of:
- A single function/method implementation
- One refactoring step (rename, extract, move)
- A bug fix with its regression test
- A documentation update

**Size guidelines:**
- Per commit: 100–300 lines preferred, 400 max
- Per PR: No hard limit, but consider splitting if >800 lines or >5 unrelated files

**Good commit scope examples:**
- `Add FastaIndex.validate() method`
- `Rename species_map → species_to_ref_fasta_map`
- `Fix off-by-one in BED coordinate parsing`

### Commit Messages

```
Concise title in imperative mood (<72 chars)

Detailed body explaining:
- What changed
- Why (link issues with "Closes #123" or "Related to #456")
- Any non-obvious implementation choices
```

### Commit Rules
- Run `uv run poe fix-and-check-all` before each commit; all checks must pass
- No merge commits
- Do not rebase without explicit user approval
- Use `git mv` for file moves; if moving *and* editing, make two commits (move first, then edits)
- **Never mix formatting and functional changes.** If unavoidable, isolate formatting into separate commits at start or end of branch.

### Pull Requests
- Title: Imperative mood, <72 chars (e.g., "Add FASTA index validation")
- Body: What changed, why, testing done, migration notes if applicable
- Link issues: "Closes #123" or "Related to #456"

### Branch Hygiene
- Use `.gitignore` liberally
- Never commit: IDE files, personal test files, local debug data, commented-out code

---

## Code Review

### As Reviewer
- Read every line of code
- Clearly distinguish suggestions from required changes; include code alternatives
- Focus on substance—avoid bikeshedding

### Review Checklist

**Correctness & Design:**
- [ ] Does the code do what it claims?
- [ ] Is it structured for testability (modular, injectable dependencies)?
- [ ] Is it appropriately generalized—not over-engineered or over-optimized?

**Readability & Style:**
- [ ] Is it readable with clear names?
- [ ] Is it idiomatic for the language?
- [ ] Would a new team member understand it without extensive context?

**Documentation & Testing:**
- [ ] Doc comments on public functions/classes?
- [ ] Code comments on non-obvious logic?
- [ ] Tests covering happy path, error conditions, edge cases?
- [ ] CHANGELOG.md updated for user-facing changes?

**Project Fit:**
- [ ] Does this code belong in this repo?
- [ ] Does it follow established patterns?

### Domain-Specific Checks

<!-- Customize for your project's domain. Examples for bioinformatics: -->

- [ ] Large file handling: streaming/chunked, not loaded into memory?
- [ ] File format edge cases handled: empty files, truncated files, malformed headers?
- [ ] Input validation performed early with clear error messages?
- [ ] Provenance preserved: input paths, parameters, versions logged where appropriate?

---

## Code Style

### Organization
- Extract logic into small–medium functions with clear inputs/outputs
- Scope variables tightly; limit visibility to where needed
- Use block comments for visual separation when function extraction isn't practical

### Naming
- Meaningful names, even if long: `species_to_ref_fasta_map` not `species_map`
- Short names only for tight scope (loop indices, single-line lambdas)
- Signal behavior in function names: `to_y()`, `is_valid()` → returns value; `update_x()` → side effect

### Documentation

**Doc comments (required on all public functions/classes):**
- What it does
- Parameters and return value
- Constraints, exceptions raised, side effects

**Code comments:**
- Explain non-obvious choices and complex logic
- Never comment self-evident code

### Type Signatures
- **Parameters:** Accept the most general type practical (e.g., `Iterable` over `List`)
- **Returns:** Return the most specific type without exposing implementation details

### Functions
- Functions should have **either** returns **or** side effects, not both
- Exceptions: logging, caching (where side effect is performance-only)

### Pragmatism
- Balance functional, OOP, and imperative—use what's clearest
- When in doubt, prefer pure functions and immutable data
- Know your utility libraries; contribute upstream rather than writing one-offs

---

## Domain Considerations

<!-- Customize for your project's domain. Examples for bioinformatics: -->

- Assume input files may be large (multi-GB); prefer streaming over loading into memory
- Validate file formats early; corrupt/truncated files are common
- Preserve provenance: log input file paths, parameters, tool versions

---

## Error Handling

- Fail fast with informative messages at I/O boundaries
- Use custom exception types for domain errors (e.g., `InvalidFastaError`)
- Never silently swallow exceptions; log or re-raise with context
- When a loop may generate multiple errors, collect them and raise once at the end
- Error messages should include: what failed, why, and how to fix (if known)

---

## External Dependencies

- Core logic must not shell out to external tools
- External tool orchestration belongs in pipeline definitions, not the toolkit
- If wrapping an external tool is necessary, isolate in a dedicated module with clear interface boundaries

---

## Performance

- Only optimize performance-critical sections (e.g., large-file processing, not config parsing)
- Workflow: profile → change → benchmark → accept or rollback
- Never guess; always measure
- Do not begin profiling or tuning without explicit user approval

---

## Testing

### Principles
- Generate test data programmatically; avoid committing test data files
- Test behavior, not implementation—tests should survive refactoring
- Cover: expected behavior, error conditions, boundary cases
- Scale rigor to code longevity: thorough for shared code, lighter for one-off scripts

### Coverage Expectations
- New public functions: at least one happy-path test + one error case
- Bug fixes: add a regression test that would have caught the bug
- Performance-critical code: include benchmark or explain in PR why not needed

---

## Documentation Maintenance

When modifying code, update as needed:
- [ ] Docstrings (if signature or behavior changed)
- [ ] CHANGELOG.md (if user-facing)
- [ ] README.md (if usage patterns changed)
- [ ] Migration notes (if breaking change)

Reference issue/PR numbers in CHANGELOG entries.

---

## Anti-patterns

| Don't | Do Instead |
|-------|------------|
| `except Exception` without re-raise | Catch specific exceptions or re-raise with context |
| Functions that mutate AND return | Separate into query (returns) and command (mutates) |
| Commented-out code | Delete it; git has history |
| `Any` type without explanation | Use `TypeVar`, `Protocol`, or add comment explaining why |
| Loading multi-GB files into memory | Stream or process in chunks |
| Vague error messages | Include file path, actual vs. expected, how to fix |

---

## Python-Specific

### Style
- Heavier use of classes and type annotations than typical Python
- Prefer `@dataclass(frozen=True)` and Pydantic models with `frozen=True`
- Isolate I/O at module boundaries; keep core logic as pure functions

### Typing
- **Required:** Type annotations on all function parameters and returns
- Annotate locals when: they become return values, or called function lacks hints
- Use type aliases or `NewType` for complex structures
- Avoid `Any`—prefer type alias or `TypeVar`
