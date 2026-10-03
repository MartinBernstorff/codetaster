# Code conventions

## Tests

- **TE-A3:** Tests should only specify literals that their outcomes depend on. Any literals that are asserted on should be assigned to a variable, and assert against that variable.
- **TE-C8:** Fakes should be stateful, and assertions should be against fake state.
- **TE-M8:** Mocking and patching is not allowed. Tests should never assert on implementation.
