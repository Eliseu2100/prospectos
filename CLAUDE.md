# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Seriax OS (the UI brand; the code, keyring service name and Electron app still say ProspectOS — don't rename those, it would orphan saved keys) is a local, single-user lead-prospecting CRM for people who sell websites to small local businesses. It is a fork of [nando0x/ProspectOS](https://github.com/nando0x/ProspectOS) (MIT). It finds businesses on Google Maps and Instagram, keeps only those with no website or a bad one, writes outreach messages with AI, and tracks each lead through a sales funnel.

The fork adds:
- Direct WhatsApp sending through a self-hosted Evolution API, plus a Telegram bot that sends the seller a daily summary (`backend/mensageiros.py`, `backend/rotas_envio.py`, `evolution/`).
- WhatsApp conversations inside the app (`sincronizacao_whatsapp.py`, `/whatsapp` inbox).
- An autopilot that contacts the best leads of an area and answers simple replies (`piloto.py`, `rotas_piloto.py`, `/piloto`).
- A choice of Gemini model in Configurações, and an Apple-style visual language (see Frontend below).

The code, comments, UI and commit messages are all in Brazilian Portuguese. Write new code in Portuguese with the same naming style, for example `obter_config`, `salvar_config`, `_validar_alvo`.

## Commands

The project is Windows-first. On this machine, `py` defaults to free-threaded Python 3.14t, which can't install the dependencies, so use the venv.

```bash
# Backend (Flask + SQLite), from backend/
py -3.14 -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python app.py                    # API at http://127.0.0.1:5000 (waitress)
PROSPECCAO_DEBUG=true .venv/Scripts/python app.py   # Flask dev server with auto-reload
.venv/Scripts/python -m pytest -q              # all tests
.venv/Scripts/python -m pytest tests/test_envio.py::TestEnvioWhatsapp -q   # a single class or test

# Frontend (React 19 + Vite + Tailwind 4 + shadcn/ui), from frontend/
npm install
npm run dev        # http://localhost:5173, proxies /api to :5000
npm run lint       # oxlint
npm run build      # tsc -b && vite build (this is also the type check)

# Both together, from the repo root (uses backend/.venv if it exists)
iniciar.bat

# WhatsApp sending (optional; needs Docker Desktop), from evolution/
copy .env.example .env   &&   docker compose up -d
```

User data (`leads.db`, backups, logs, Instagram session) lives in `%LOCALAPPDATA%\SeriaxOS`, not in the repo. `iniciar.bat` sets `PROSPECCAO_DIR_DADOS`, which `paths.py` reads, because the repo sits inside OneDrive and OneDrive locks `leads.db` while syncing, causing random "database is locked" errors. On the first start with that variable, `paths.migrar_dados_da_pasta_antiga` copies the old data over and renames `backend/leads.db` to `leads.db-antigo`. Without the variable (tests, plain `app.py`), the data stays in `backend/`. The app log is `%LOCALAPPDATA%\SeriaxOS\logs\prospeccao.log`.

Maps searches can be cancelled with `POST /api/buscar/cancelar`. `jobs.cancelar_busca` sets an event that progress callbacks check (`BuscaCancelada`) and kills the scraper process. A "ghost" search, whose flag is on but whose thread is dead, is reset directly.

`app.py` calls `truststore.inject_into_ssl()` before anything else, so Python trusts the Windows certificate store. Kaspersky on this machine intercepts HTTPS with its own root CA; without truststore, `requests` calls fail at random with "self-signed certificate in certificate chain". Verification stays on. Note that api.telegram.org is blocked on this network at the TCP level, which truststore cannot fix.

Instagram login is broken upstream as of 2026-10. Instagram answers `needs_upgrade` to every instagrapi version, including 3.2.2 / app 449 (instagrapi issues #2807 and #2881). The fix is to bump `instagrapi` in `requirements.txt` once a release fixes it. `rotas_instagram.traduzir_erro_login_instagram` logs `error_type`/`message` from `last_json` (never the password).

`google-maps-scraper.exe` (from gosom/google-maps-scraper) is not committed. It must sit next to `backend/app.py` for the scraper source of the Google Maps channel. The official Places API is the alternative source.

## Architecture

**Backend (`backend/`).** `app.py` registers one Flask blueprint per area: `rotas_leads` (Maps CRM and search), `rotas_instagram`, `rotas_analytics`, `rotas_config`, `rotas_conversa` (conversation cockpit) and `rotas_envio` (WhatsApp/Telegram sending). Each blueprint opens its own short-lived SQLite connection through `db.conectar()`.

- **Schema and migrations** live in `processar.preparar_banco` / `migrar_banco`. Migrations are additive and idempotent and run on every startup. Add new columns there, never by recreating tables.
- **Config and secrets** go through `db.obter_config` / `db.salvar_config`. The lookup order is the OS keyring (only for keys in `db.CHAVES_SECRETAS`), then the `configuracoes` table, then env vars / `.env`. Any new secret must be added to `CHAVES_SECRETAS` so it never lands in `leads.db`, because the database is copied into backups.
- **AI** (`ia.py`): every use (Maps copy, Instagram DM, profile classification, conversation analysis) goes through `executar_com_fallback`. It tries Gemini → Claude → Groq → NVIDIA, skips providers without a key, and puts providers that hit a 429 into a 5-minute cooldown. Claude (`claude-haiku-5-5`, a paid key) comes right after Gemini because the user wants no low-quality or missing replies to clients; it rejects `temperature`, so `claude_gerar_mensagem` ignores that argument and tunes `output_config.effort` instead. Each provider also falls back between its own models: Gemini switches to Flash-Lite on a 503, and Groq walks `MODELOS_GROQ` when a model is retired. Prompts come in (system, user) pairs. Anything that needs variety (closing line, suggested time) is randomized in Python, not left to the model.
- **Long-running work** (scraper runs, Instagram analysis) runs as background jobs in `jobs.py`. Job state is persisted, and jobs interrupted by a restart are marked on startup.
- **Two lead tables with incompatible keys**: `leads` uses `place_id TEXT` (Maps), and `instagram_leads` uses `id INTEGER`. Cross-channel tables (`mensagens_conversa`, `analises_conversa`) address leads by `(canal, lead_ref)` with no foreign key. Validate with `rotas_conversa._validar_alvo`.
- **Conversation history** sources are tracked by `origem`: `whatsapp` (passively captured from the Electron WhatsApp window), `manual`, or `app` (sent by ProspectOS through Evolution). The daily send limit in `rotas_envio` counts `origem='app'` rows written today. Sending is one lead per user click by design; there is no bulk send.
- **WhatsApp inside the app** (`sincronizacao_whatsapp.py`): a background thread, started only under `__main__` in `app.py` and never in tests, polls the Evolution API every 60s. It does this for leads that are past `novo` or already have messages, querying both phone JIDs (with and without the 9th digit) plus `leads.whatsapp_jid`, the JID returned by the send call, which may be an `@lid`. Messages are stored with `chave_dedup = "wa:<id>"`, the same key the app's send path uses, so they are never duplicated. A new message from the lead moves `novo`/`contatado` to `respondeu`. The open conversation page also syncs that one lead every 8s. When Evolution is connected, the UI sends inside the app, using the `/whatsapp` inbox and `/conversas/:placeId`, instead of opening wa.me links (`useWhatsappConectado`, `BotaoWhatsappLead`).
- **Autopilot** (`piloto.py`): a background thread (every 20s, `__main__` only) that does two things. First, when `piloto_ativo` is on, it sends a first contact to the highest-`SQL_SCORE` `novo` lead matching the area (`piloto_nicho`/`piloto_cidade` LIKE on nicho+categoria / cidade+endereco), using `rotas_leads.gerar_copy_para_lead` + `rotas_envio.enviar_e_registrar`. Second, it auto-replies to leads with `piloto_status='automatico'` whose last message is from the lead, using `ia.decidir_resposta_piloto` (JSON: `responder | passar_para_humano | encerrar`). Safety rules live there and are tested in `tests/test_piloto.py`: business-hours window, random interval between contacts, the shared daily limit, a keyword opt-out fast path that never calls the AI, a max of consecutive auto-replies, and handing off to the seller (`piloto_status='humano'`) on price/closing/doubt, or whenever the seller writes manually (app send or phone). The settings are `piloto_*` keys in `configuracoes`; actions are logged in `piloto_eventos`.
- **@lid addressing and business bots**: since 2026, WhatsApp delivers many replies with `remoteJid=<code>@lid` and the phone number only in `key.remoteJidAlt`. `sincronizacao_whatsapp.consultas_do_lead` queries every phone JID by both `remoteJid` and `remoteJidAlt`, and saves the discovered `@lid` in `leads.whatsapp_jid`. Most first "replies" are WhatsApp Business auto-responders, which `e_resposta_automatica` detects from phrases plus reply speed, tuned on the real messages of 2026-10-28. They are stored with `mensagens_conversa.automatica = 1`, and they never count as a reply: no `respondeu` status, no autopilot answer, no alert, and the inbox ignores them. `reclassificar_respostas_automaticas()` re-applies the rules on every startup.
- **First-contact copy**: `ia.nome_curto_empresa` strips the SEO suffix from Google names before prompting. A first message longer than `MAX_CARACTERES_PRIMEIRA_MENSAGEM` (350) gets one automatic "encurte" call. Rules ban tech jargon ("código limpo", SEO, etc.) and greeting a business name as a person.
- **Outreach method** (`abordagem.py`): the first message never sells. It fits one phone screen, asks one question, and uses a real fact about the lead. Python picks the opening structure from the lead's data (`escolher_estrutura_abertura`). Follow-ups follow `CADENCIA_FOLLOWUP_DIAS` (D2/D5/D9/D14 after the first contact, the last one being a goodbye) with a new angle each time. `GUIA_OBJECOES` is injected into the autopilot reply prompt. The niche "pain" comes from an optional local file, `playbook_nichos.json` in the data folder, which is gitignored and must never be committed because it comes from the user's personal-use material. Without it, everything works without the niche pain. The autopilot sends due follow-ups before new first contacts, in the same paced slot and daily limit (`piloto_followup`). It also sends one Python-written note to leads answered only by a business bot, asking for the owner (`piloto_recado_robo`).
- **Lead list order**: the default `/api/leads` order is recent activity (`atualizado_em`), so a lead whose status changed shows up at the top. `ordenar=encontrados` keeps the old order. Kanban loads every page, because each column needs all leads.
- **Phone numbers**: the database stores DDD + number, while WhatsApp uses DDI 55 and sometimes drops or adds the 9th digit. Use `rotas_conversa.normalizar_telefone` / `_variantes_telefone` for matching and `mensageiros.numero_internacional` for sending.

**Tests** use Flask's `test_client`. They point `db.CAMINHO_BANCO` at a `tmp_path` database and monkeypatch the keyring helpers (`db._keyring_obter`/`_salvar`/`_apagar`) with a dict. AI calls and HTTP (`requests`) are monkeypatched. Tests never touch the network or the real keyring; copy the `banco` and `cliente` fixtures from an existing test file.

**Frontend (`frontend/src/`).** The visual language follows the user's Apple-style DESIGN.md. The tokens live in `index.css`: page `#f5f5f7` with white cards and no shadows or borders (`rounded-2xl`/`rounded-[28px] bg-card`), ink `#1d1d1f`, and a single blue accent `#0071e3` for primary actions. Buttons, selects and badges are pills (`rounded-full`). The font stack is SF Pro, then Inter. Keep channel colors (Maps/Instagram gradients) only on small icon tiles, never on surfaces. `pages/` hold the screens. Each API area follows the same pattern: a `services/*Service.ts` that wraps `httpClient`, which turns the backend's `{"erro": "..."}` into `ApiError`; `hooks/use*.ts` with React Query queries and mutations that show a sonner toast on success or error; and components under `components/<area>/`. The UI talks to the backend only through relative `/api/*` URLs, so the same build works under Vite dev, under Flask serving `frontend/dist`, and inside Electron.

**Desktop (`desktop/`).** An Electron shell that spawns the PyInstaller backend build (`backend/prospectos.spec`) and reads `LISTENING_ON=<port>` from its stdout. It also hosts an internal WhatsApp Web window whose `preload-whatsapp.js` reports the open chat to `/api/conversa/ingestao`. The installer is built with Inno Setup from `instalador/prospectos.iss`. `electron-builder.yml` still publishes and auto-updates from `nando0x/ProspectOS`; change `publish.owner`/`repo` before publishing releases from this fork.
