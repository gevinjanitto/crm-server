# PRD — CRM Maiharta (clone of gevinjanitto/crm-server)

## Original problem statement
Clone https://github.com/gevinjanitto/crm-server. Personal notes must have the same features as the regular notes, just without the tag feature. Build the features from SPEC_AI_ASSISTANT_MCP.md, with an on/off switch in admin. Also create a downloadable setup.sh that contains every project file so it can run locally. Do not change anything else.

## User choices
- AI provider: OpenAI-compatible (default SumoPod), configurable from Admin or .env (AI_BASE_URL, AI_API_KEY, AI_MODEL)
- Phases 1–5, including OAuth 2.1 for ChatGPT
- One main switch for all AI features
- Database stays MySQL/MariaDB

## Architecture
React (CRA + yarn) + FastAPI + MariaDB (docstore.py, a Mongo-style API on top of MySQL).
New backend files: ai_settings.py (toggle + config), api_tokens.py (PAT plus principal/rate limit), ai_tools.py (14 tools, POST /api/ai/tools/{name}), mcp_server.py (JSON-RPC Streamable HTTP /api/mcp), oauth.py (DCR, PKCE S256, authorize/consent, token/refresh/revoke, .well-known under /api), assistant.py (/api/assistant/chat + /action, function calling).
Personal notes: /api/personal-notes CRUD + versions; the old single note migrates automatically.
Frontend: PersonalNotes (reuses DocEditor `personal` = no @mention/visibility), assistant/* (header button + Sheet panel), settings/AiAdminSettings, ApiTokens, AdminTokens, pages/OAuthAuthorize.
setup.sh: scripts/build_setup.sh builds a self-extracting /app/setup.sh and frontend/public/setup.sh (download at /setup.sh).

## Implemented (2026-06)
- Personal notes with the same features as project notes, without the tag feature
- AI master toggle (admin), PAT (hashed, shown once, max 10, revocable, audited), tools that respect role/project_scope, MCP server, OAuth for ChatGPT, Assistant panel + quick-action chips
- DEPLOY_IDCLOUDHOST.md §14 "Menghubungkan ChatGPT/Claude"; tests backend/tests/test_ai_assistant_mcp.py
- Tested: iteration_1 — all flows pass; minor issues fixed (write tools POST-only, bool coercion, token-limit expiry, rate-limit pruning, label fixes)

## Backlog
- P1: Test with a real SumoPod key; streaming replies in the assistant
- P2: Hide or clean up revoked tokens; Settings layout balance; conversation history UI
- Known pre-existing: the tiptap editor loses input when typing very fast right after the Checklist tool (also in project Notes)
