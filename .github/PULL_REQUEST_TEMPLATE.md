## Summary

<!-- What does this PR implement? Link the issue. -->

Refs #

## Spec Compliance

<!-- For every formula this PR implements or touches, fill one row.
     Delete this table if the PR touches no spec formulas (e.g. pure infra). -->

| Spec section | Documented or Engineering Choice? | Worked example reproduced? |
|---|---|---|
| e.g. §4 NSI | Documented | Yes — NSI=0.152 test passes |

## Engineering choices introduced

<!-- List any new thresholds/constants not in the spec, and your reasoning. -->

-

## Testing

<!-- How did you verify this works? Paste relevant test output if useful. -->

- [ ] Unit tests added/updated
- [ ] Worked numeric examples from spec pass as test fixtures
- [ ] Ran locally against mock data end-to-end (if applicable)

## Checklist

- [ ] I read the relevant section(s) of `docs/NDS_SPEC.md` before implementing
- [ ] All price displacement math uses log scale (spec §1)
- [ ] No hardcoded magic numbers — engineering-choice constants live in config with comments
- [ ] I did not modify `docs/NDS_SPEC.md` without prior discussion in an issue
