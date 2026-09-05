# ERPNext-test authorization synchronization hotfix 0.5.1

Date: 2026-09-05

Status: **IN PROGRESS — DEPLOYMENT AND LIVE RETRY PENDING**

The canonical ERPNext-test user update was saved, but the authorization source
job rejected the valid Unicode role `品管` before applying the explicit role
mapping. After the sender repair, delivery reached LaunchFlow and returned 403
because the same canonical internal User already held System Manager. Separate
unmapped-user deliveries returned 500 because a disabled absent target was
modeled as a required Link to User.

The bounded repair accepts valid Unicode ERPNext source-role names while still
emitting only explicit mapping values, permits the ERPNext authorization owner
to adopt an existing canonical internal User, protects the built-in and
transport service identities, and stores absent target identity as Data so a
disabled projection remains durable and auditable.

Production ERPNext is not contacted. Authorization enforcement remains off.
Project, Customer, Supplier and Item Group synchronization are not part of this
hotfix and no mapping is guessed.

The first exact-SHA Level 3 run identified only two unregistered synthetic
credential fingerprints from the predecessor Item adapter test. Both are fixed
test values bound to `.invalid` configuration; their exact historical
fingerprints are added to the existing reviewed allowlist before the unchanged
gate is repeated.
