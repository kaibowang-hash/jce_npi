---
name: industrial-ux
description: Design or review the Siemens-style industrial UX for NPI One, including square geometry, restrained palette, App Shell, worklists, object pages, project/tooling/trial workspaces, states and accessibility. Use for every end-user UI task.
---

# Industrial UX

## Goal
Create a classic, professional engineering product based on Siemens Industrial Experience patterns, not a collection of Frappe forms or colorful SaaS cards.

## Before designing
- Read `docs/UX_INTERACTION_SPEC.md`, `design/UI_VISUAL_BASELINE.md`, `design/design-tokens.json`, and the related domain spec.
- Identify persona, job, context object and lifecycle state.
- Confirm which data is NPI-owned, ERP-owned, computed or stale.
- List normal, empty, loading, error, no-permission, read-only, conflict and async states.
- State the proposed shell/tree/table/inspector layout and why it matches the engineering task.

## Required patterns
- Fixed App Shell with rectangular domain navigation and stable toolbar.
- Single industrial teal primary + neutral surfaces; semantic colors only for small status emphasis.
- Default 0–2px radius; no card wall, gradient, glass effect, strong shadow or decorative illustration.
- Worklist/tree-table for queues and cross-object work.
- Object Page for Project/Tooling/Trial/Change.
- Resizable split panes and docked inspector for engineering workspace.
- Route compact icon-first secondary actions only through the repository-owned
  local icon adapter. Give every icon-only action a translated accessible name
  and tooltip, keyboard access, visible focus, disabled state and a non-hover
  discovery path. Retain visible text for primary, high-risk or ambiguous
  actions. Keep Siemens as the sole primary design baseline; do not copy
  GitHub branding, import vendor icons directly or add unapproved
  Primer/Octicons.
- Impact Review for high-risk commands.
- One visual primary action.
- SourceBadge + SyncBadge for shared objects.
- Domain ViewModels from BFF, not raw DocType joins in the browser.

## Review questions
- Does the screen look like classic engineering software rather than a consumer SaaS dashboard?
- Is at least 85% of the visual area neutral?
- Are ordinary component radii 0–2px and panels free of shadow?
- Can the user complete the common task from My Work/Project Cockpit with <=2 context changes?
- Is object identity, version, status, source and editability obvious?
- Is the next action clear without reading a manual?
- Does the page preserve context after drilldown?
- Are failures and partial execution honest?
- Is status understandable without color?
- Does keyboard/focus behavior work?
- Do icon-only actions have translated names/tooltips and non-hover discovery,
  while primary, high-risk and ambiguous actions retain visible text?
- Are all icons routed through the local adapter with no GitHub branding,
  direct vendor import or unapproved Primer/Octicons dependency?
- Is a Desk page leaking into the primary flow?

## Evidence
Provide realistic fixtures and screenshots/stories at 1366×768 and 1920×1080, including 125%/150% zoom. Map each UI state to acceptance tests. Visual review must explicitly report palette usage, radius, shadow, density, hierarchy and mixed-language findings.
