# Security policy

## Reporting

Do not open a public issue containing a credential, private dataset, personal data, or an exploitable vulnerability. Contact the repository maintainers privately and include reproduction details without the sensitive value.

## Secrets

Keep `.env` files local. Use `.env.example` for documentation. `VITE_*` variables are shipped to the browser and must never contain secrets. If a credential was committed, revoke it immediately, then remove it in a follow-up commit or history rewrite coordinated with maintainers.

## Scope

CausalAtlas is research software. It is not a clinical decision system and must not be used as a substitute for expert review or regulatory validation.
