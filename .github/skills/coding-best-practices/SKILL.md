---
name: coding-best-practices
description: "Use when writing, reviewing, debugging, or refactoring code to apply engineering best practices for correctness, maintainability, security, and testability."
---

# Coding Best Practices

## When to Use

Use this skill when you need to:
- write new code or modify existing code
- review implementation quality before merging
- debug or refactor a bug-prone area
- improve readability, safety, test coverage, or maintainability
- check whether a solution meets engineering standards

## Goal

Produce software that is correct, understandable, testable, secure, and easy to evolve without unnecessary complexity.

## Core Principles

Apply these design principles as part of every implementation or review:

### SOLID
- Single Responsibility: each class/module should have one reason to change.
- Open/Closed: extend behavior without modifying existing stable code unnecessarily.
- Liskov Substitution: derived types must be usable where base types are expected.
- Interface Segregation: avoid forcing consumers to depend on methods they do not use.
- Dependency Inversion: depend on abstractions, not concrete implementations.

### DRY
- Do not repeat logic that can be centralized.
- Extract shared behavior into helpers, modules, or well-named abstractions.
- Reduce duplication without creating unnecessary indirection.

### KISS
- Prefer the simplest solution that satisfies the requirement.
- Avoid complexity that is not justified by real needs.

### YAGNI
- Do not add speculative features or abstractions before they are required.
- Build only what is needed for the current problem.

### OOP / Object-Oriented Design
- Model responsibilities around real concepts and behaviors.
- Keep data and behavior cohesive.
- Favor composition where it keeps code flexible and understandable.
- Avoid deep inheritance chains or god classes.

### Separation of Concerns
- Keep different responsibilities in separate layers, modules, or functions.
- Let each component handle one concern clearly.

### Encapsulation and Cohesion
- Hide internal state when not needed.
- Group related behavior together so the design stays understandable.

### Maintainability and Readability
- Prefer descriptive naming, clear structure, and consistent style.
- Write code that a teammate can understand quickly without needing a large amount of context.

### Clean Code
- Favor obvious names, small functions, and direct logic.
- Prefer explicit code over cleverness or hidden behavior.
- Remove friction from reading and maintaining the solution.

### Design Patterns and Architecture
- Use established patterns only when they add clarity or solve a real problem.
- Prefer simple, domain-aligned architecture over over-engineering.
- Keep dependencies and interactions understandable.

### Scalability and Extensibility
- Design for change without making the code brittle.
- Avoid hard-coded assumptions that block future growth.
- Choose boundaries that allow evolution without large rewrites.

## Workflow

### 1. Understand the requirement before changing code
- Identify the actual problem, desired behavior, and constraints.
- Confirm input/output expectations, edge cases, error handling, and external dependencies.
- If requirements are unclear, ask clarifying questions before implementing.

### 2. Keep the scope small and explicit
- Prefer the smallest change that solves the root cause.
- Split large tasks into focused, reviewable steps.
- Avoid broad refactors unless they are needed for correctness or maintainability.

### 3. Design a minimal, robust solution
- Choose the simplest approach that satisfies the requirement.
- Prefer clear, idiomatic patterns over clever or overly abstract solutions.
- Consider failure modes, configuration, boundary conditions, and future extension.
- Follow the project’s conventions for naming, structure, and architecture.

### 4. Implement with quality in mind
- Write readable, self-explanatory code with clear function boundaries.
- Keep functions focused and responsibilities separated.
- Validate assumptions with explicit checks and helpful error messages.
- Handle edge cases, invalid input, and failure paths intentionally.
- Avoid duplicated logic; prefer reusable abstractions when they improve clarity.
- Keep code consistent with the local style and existing patterns.

### 5. Make correctness observable
- Add or update tests for behavior changes.
- Prefer failing tests before the fix when debugging a defect.
- Cover the happy path, edge cases, and regression scenarios relevant to the change.
- Verify that the change is not only compiling but actually behaves as expected.

### 6. Validate before considering the task complete
- Run the smallest relevant checks: unit tests, integration tests, linting, type checking, or a focused build.
- Confirm the fix addresses the original issue and does not introduce regressions.
- If validation fails, fix the root cause rather than masking the symptom.

### 7. Review for quality and maintainability
- Check for readability, naming, complexity, and accidental coupling.
- Remove dead code, debug statements, or temporary shortcuts that are not part of the final solution.
- Ensure comments explain intent, not obvious implementation details.
- Verify that documentation and public contracts are kept in sync with the code.

## Decision Points

- If the requirement is ambiguous: pause and clarify before coding.
- If the bug is not reproduced: inspect the root cause and add a minimal reproduction or failing test.
- If the scope is large: break it into smaller incremental changes.
- If the fix is complex: simplify the design or document trade-offs before proceeding.
- If the code is hard to understand: refactor for clarity, not for style alone.
- If security or reliability concerns appear: address them before finishing the task.
- If performance matters: measure and optimize only the relevant bottleneck.

## Quality Criteria

A solution is ready when all of the following are true:
- The requirement is clearly understood and implemented.
- The code is readable, maintainable, and consistent with the repo’s style.
- Important edge cases and error paths are handled.
- Tests or validation cover the change and relevant regressions.
- Security, reliability, and performance concerns have been considered.
- No unnecessary complexity or dead code remains.
- The change is easy for a teammate to review and reason about.

## Anti-Patterns to Avoid

- shipping code without understanding the real problem
- broad refactors mixed with unrelated changes
- writing clever solutions instead of clear ones
- skipping tests for bug fixes or behavior changes
- ignoring edge cases and invalid inputs
- masking failures instead of handling them properly
- adding unnecessary abstractions or premature optimization
- leaving debugging artifacts or commented-out code in place

## Completion Checklist

Before finishing a task, verify:
- [ ] The change matches the requirement.
- [ ] The design is minimal and understandable.
- [ ] Error handling is explicit and safe.
- [ ] Relevant tests were added or updated.
- [ ] Validation commands were run and passed.
- [ ] The code is clean, readable, and reviewable.
- [ ] No obvious security or maintainability issues remain.
- [ ] The solution respects the core principles: SOLID, DRY, KISS, YAGNI, and clear OOP boundaries.
- [ ] The code is easy to extend without introducing unnecessary coupling or duplication.

## Code Review Checklist

Use this checklist when reviewing or evaluating a change:
- [ ] Does the code satisfy the requirement without overbuilding?
- [ ] Are responsibilities separated and the design understandable?
- [ ] Is duplication minimized without creating needless abstraction?
- [ ] Are class/module boundaries aligned with SRP and cohesion?
- [ ] Are dependencies managed in a way that keeps the system flexible?
- [ ] Are edge cases and failure paths handled intentionally?
- [ ] Are tests adequate for the behavior and regression risk?
- [ ] Is the code clearer than the alternative?

## Example Prompts

- "Review this change against coding best practices and suggest improvements."
- "Refactor this function to improve readability and reliability without changing behavior."
- "Find the root cause of this bug and implement the smallest correct fix with tests."
- "Assess whether this code follows good engineering practices for error handling, security, and maintainability."
- "Propose a minimal, well-tested implementation for this feature request."

## Related Customizations

- Add repo-specific instructions for architecture, style, or testing conventions.
- Pair this skill with a lint or test workflow prompt for validation.
- Create a code-review skill that applies the same quality checklist during PR review.
