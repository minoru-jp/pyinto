# English Documentation Translation Status

The Japanese canonical sources in `devdocs/canonical_sources/`, rendered as `devdocs/canonical_documents/`, remain authoritative. The published English documents are maintained derivatives, not a second source of technical contracts.

## Current coverage

**Unabridged English text is present for all 15 published documents:** README, STATUS, CHANGELOG, Glossary, four Specification documents and their index, and all five Realizer guides/references and their index. The two runnable Target examples preserve their original Python code. The Composition, Construct Model, and Python Frontend specifications retain each clause, normative level, conditions, and related references. STATUS retains five sections and 138 entries; CHANGELOG retains all 128 Added, 79 Changed, and 5 Removed entries.

**Translation coverage is complete, but automated checks do not certify semantic equivalence.** Technical/editorial review against the Japanese canonical documents remains important before an external public release. Structural parity and SHA-256 tracking detect omission patterns and stale derivatives, not nuanced mistranslations.

## Maintenance workflow

1. Edit `devdocs/canonical_sources/`, not generated Japanese documents or English files, when changing a technical contract.
2. Regenerate and check Japanese canonical Markdown using `python scripts/docs.py render` and `python scripts/docs.py check` (requires the development environment with shikumi-devdoc).
3. Update affected published English documents, preserving contract identifiers, links, and executable snippets.
4. Review technical equivalence and terminology. `python scripts/published_docs.py record` writes the manifest's *source and derivative hashes* after review; it does not translate or attest correctness automatically.
5. Run `python scripts/published_docs.py check`. A changed Japanese or English document invalidates its stored hash, exposing out-of-sync translations. This also validates internal links, Markdown code fences, presence of contract IDs, and the Construct variant table. The completed Composition, Construct Model, and Python Frontend translations additionally check clause title/level/link-field parity. The translated STATUS and CHANGELOG are also checked for section and entry counts; CHANGELOG contract identifiers are checked per entry. None of these mechanical checks substitutes for editorial review of semantic accuracy.
6. Run `python scripts/published_docs.py release-check` before claiming the entire English publication is complete. This now succeeds because all entries are marked `translated`, but the result is not an independent semantic review.
7. Run documentation tests and build the wheel/sdist to verify `README.md` is used as the package's English long description.

The `devdocs/config/published_en.json` manifest records the source/derivative mapping and editorial coverage state. Translation is not automated: checksum equality only confirms which revisions were paired, never their semantic equivalence.
