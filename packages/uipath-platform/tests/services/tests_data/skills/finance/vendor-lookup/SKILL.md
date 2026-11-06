---
name: vendor-lookup
description: Find the canonical vendor record and its payment terms before acting on an invoice. Use when a vendor name, tax id or supplier number appears.
---

# Vendor lookup

1. Normalize the name you were given: trim legal suffixes (Inc, LLC, Corp, Ltd) and casing.
2. Query the agent's vendor directory tool by tax id when present, otherwise by normalized name.
3. If exactly one record matches, return: canonical name, vendor id, payment terms, and whether the vendor is on hold.
4. If several match, return the candidates with their tax ids and ask the caller to disambiguate. Do not guess.
5. If none match, return `vendor-not-found` and the normalized name you searched for.

Do not create vendor records from this skill.
