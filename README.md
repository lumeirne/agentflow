# 🤖 AgentFlow

**Multi-service productivity co-pilot powered by Auth0 Token Vault**

AgentFlow is an intelligent agent that securely connects to your favorite services (Google, GitHub, Slack) via Auth0 and performs complex workflows across these platforms. Using LangGraph and AI, it helps you automate scheduling, email drafting, pull request reviews, and more.

---

## ✨ Features

- **Auth0 Token Vault Integration** — Securely manage OAuth tokens for multiple services
- **Multi-Service Support** — Google Calendar, Gmail, GitHub, Slack
- **Agent Workflows** — LangGraph-powered AI agent with custom tools
- **Real-time Updates** — WebSocket support for live workflow monitoring
- **Approval System** — Request human review for sensitive actions
- **Identity Mapping** — Connect Auth0 identities to service accounts
- **Settings Management** — User preferences for scheduling and automation

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                      │
│           User Interface + Real-time WebSocket              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Backend (FastAPI)                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ API Routes:                                          │  │
│  │ • /api/auth - Auth0 & Token Management              │  │
│  │ • /api/runs - Workflow Execution & Monitoring        │  │
│  │ • /api/approvals - Approval Workflow                │  │
│  │ • /api/settings - User Settings                     │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Agent Engine (LangGraph):                            │  │
│  │ • Graph-based workflow execution                     │  │
│  │ • Tool integration & branching                       │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   ┌────▼──┐      ┌────▼──┐     ┌────▼──┐
   │ Auth0 │      │Google │     │GitHub │
   │       │      │  APIs │     │ APIs  │
   └───────┘      └───────┘     └───────┘
        │
   ┌────▼──┐
   │ Slack │
   │ APIs  │
   └───────┘
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Node.js 18+ & npm**
- **Auth0 Account** (free tier available)
- External API Keys: Google Cloud, GitHub, Slack, OpenRouter

### 1. Clone & Install Dependencies

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 2. Configure Environment Variables

Create a `.env` file in the **root directory** with the following:

```env
# ─── Database ───
DATABASE_URL=sqlite+aiosqlite:///./agentflow.db

# ─── Auth0 ───
AUTH0_DOMAIN=<your-auth0-domain>.us.auth0.com
AUTH0_CLIENT_ID=<your-client-id>
AUTH0_CLIENT_SECRET=<your-client-secret>
AUTH0_AUDIENCE=https://<your-auth0-domain>.us.auth0.com/api/v2/

# ─── LLM (OpenRouter) ───
OPENROUTER_API_KEY=sk-or-v1-<your-api-key>
OPENROUTER_MODEL=nvidia/nemotron-3-super-120b-a12b:free

# ─── App ───
SECRET_KEY=<change-me-in-production>
APP_BASE_URL=http://localhost:3000
API_BASE_URL=http://localhost:8000
```

### 3. Environment Variables Explained

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `AUTH0_DOMAIN` | Your Auth0 tenant domain | [Auth0 Dashboard](https://manage.auth0.com) → Applications → Settings |
| `AUTH0_CLIENT_ID` | OAuth App Client ID | [Auth0 Dashboard](https://manage.auth0.com) → Applications → Your App → Settings |
| `AUTH0_CLIENT_SECRET` | OAuth App Client Secret | [Auth0 Dashboard](https://manage.auth0.com) → Applications → Your App → Settings |
| `AUTH0_AUDIENCE` | Management API Audience | `https://<your-domain>.us.auth0.com/api/v2/` |
| `OPENROUTER_API_KEY` | LLM API Key | [OpenRouter](https://openrouter.ai) → API Keys |
| `OPENROUTER_MODEL` | LLM Model to use | See [Available Models](https://openrouter.ai/models) |
| `SECRET_KEY` | JWT signing secret | Generate a random string (keep secure in production) |

---

## 📋 Setup Steps (Detailed)

### Step 1: Auth0 Configuration

1. Create a [Free Auth0 Account](https://auth0.com)
2. Create a new **Regular Web Application** named "AgentFlow"
3. Configure Allowed URLs:
   - **Callback URLs**: `http://localhost:3000/api/auth/callback`
   - **Logout URLs**: `http://localhost:3000/`
   - **Web Origins**: `http://localhost:3000`
4. Enable Auth0 Management API access:
   - Go to **Applications > APIs > Auth0 Management API**
   - Switch to **Machine to Machine Applications** tab
   - Authorize your "AgentFlow" app
   - Grant scope: `read:user_idp_tokens`

### Step 2: Google Cloud Setup (Optional - for Calendar & Gmail)

1. Create a [Google Cloud Project](https://console.cloud.google.com)
2. Enable APIs: **Google Calendar API** & **Gmail API**
3. Create **OAuth 2.0 Credentials** (Web Application)
4. Redirect URI: `https://<YOUR_AUTH0_DOMAIN>/login/callback`
5. In Auth0, create a **Google/Gmail Social Connection** with these credentials

### Step 3: GitHub Setup (Optional - for PR Review)

1. Go to GitHub Settings → **Developer settings** → **OAuth Apps** → **New OAuth App**
2. Authorization callback URL: `https://<YOUR_AUTH0_DOMAIN>/login/callback`
3. In Auth0, create a **GitHub Social Connection** with these credentials

### Step 4: Slack Setup (Optional - for Messaging)

1. Create a [Slack App](https://api.slack.com/apps)
2. Go to **OAuth & Permissions** and add scopes: `chat:write`, `users:read`, `channels:read`, `groups:read`
3. Add **Redirect URL**: `https://<YOUR_AUTH0_DOMAIN>/login/callback`
4. In Auth0, configure Slack as a **Custom Social Connection**

---

## ▶️ Running the Application

### Terminal 1: Start Backend API

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend will run at: **http://localhost:8000**  
API Docs: **http://localhost:8000/docs**

### Terminal 2: Start Frontend

```bash
cd frontend
npm run dev
```

Frontend will run at: **http://localhost:3000**

### Verify Setup

1. Open http://localhost:3000
2. Click "Login" and authenticate with Auth0
3. Navigate to **Settings** → **Connections** to link external services
4. Test by creating a workflow in **Runs**

---

## 📁 Project Structure

```
agentflow/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Configuration & environment variables
│   ├── database.py          # SQLAlchemy setup & initialization
│   ├── agent/               # LangGraph agent implementation
│   │   ├── graph.py         # Workflow graph definition
│   │   ├── nodes.py         # Graph node implementations
│   │   ├── prompts.py       # AI prompts for agent reasoning
│   │   └── state.py         # Agent state schema
│   ├── api/                 # Endpoint routers
│   │   ├── auth.py          # Authentication endpoints
│   │   ├── runs.py          # Workflow execution endpoints
│   │   ├── approvals.py     # Approval workflow endpoints
│   │   └── settings.py      # Settings management endpoints
│   ├── auth/                # Auth0 integration
│   │   ├── middleware.py    # JWT validation middleware
│   │   ├── dependencies.py  # Auth dependencies
│   │   └── token_vault.py   # Token management
│   ├── models/              # SQLAlchemy models (database schema)
│   ├── services/            # Business logic & external API integration
│   │   ├── github_service.py
│   │   ├── google_service.py
│   │   ├── slack_service.py
│   │   ├── llm_service.py
│   │   ├── workflow_service.py
│   │   └── approval_service.py
│   ├── tools/               # LLM tools & integrations
│   ├── utils/               # Logging, redaction, helpers
│   ├── workers/             # Background job execution
│   ├── websocket/           # Real-time updates
│   └── requirements.txt     # Python dependencies
│
├── frontend/
│   ├── app/                 # Next.js app directory pages
│   │   ├── page.tsx         # Dashboard
│   │   ├── approvals/       # Approval management
│   │   ├── connections/     # Service connections
│   │   ├── runs/            # Workflow runs
│   │   └── settings/        # User settings
│   ├── components/          # React components
│   ├── hooks/               # Custom React hooks
│   ├── lib/                 # Utilities & API clients
│   └── package.json         # Node dependencies
│
└── README.md                # This file
```

---

## 🔌 API Endpoints

### Authentication
- `POST /api/auth/login` — Initiate Auth0 login
- `GET /api/auth/callback` — OAuth callback handler
- `GET /api/auth/profile` — Get current user profile
- `GET /api/auth/connections` — List connected services

### Workflow Execution
- `GET /api/runs` — List all workflow runs
- `POST /api/runs` — Create new workflow run
- `GET /api/runs/{id}` — Get run details & logs
- `PATCH /api/runs/{id}/cancel` — Cancel running workflow

### Approvals
- `GET /api/approvals` — List pending approvals
- `POST /api/approvals/{id}/approve` — Approve action
- `POST /api/approvals/{id}/reject` — Reject action

### Settings
- `GET /api/settings` — Get user settings
- `PATCH /api/settings` — Update settings

Full API documentation available at **http://localhost:8000/docs** (Swagger/OpenAPI)

---

## 🛠️ Technology Stack

### Backend
- **FastAPI** — Modern async web framework
- **SQLAlchemy** — ORM for database
- **LangGraph** — Agent workflow orchestration
- **Auth0** — Authentication & token management
- **WebSockets** — Real-time updates

### Frontend
- **Next.js 16** — React framework with SSR
- **TypeScript** — Type safety
- **Auth0 SDK** — Authorization
- **Tailwind CSS** — Styling
- **Zustand** — State management

### External Services
- **Auth0** — Identity & OAuth token vault
- **Google APIs** — Calendar, Gmail
- **GitHub API** — Repository data, PRs
- **Slack API** — Messaging, users
- **OpenRouter** — LLM API access

---

## 🚨 Troubleshooting

### Backend won't start
```bash
# Check Python version (3.11+ required)
python --version

# Reinstall dependencies
pip install -r backend/requirements.txt

# Check if port 8000 is in use
netstat -ano | findstr :8000
```

### Frontend build fails
```bash
# Clear cache and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Database locked
```bash
# Remove old database file and restart
rm agentflow.db
python backend/main.py
```

### Auth0 login not working
1. Verify `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` in `.env`
2. Check Allowed Callback URLs in Auth0 Dashboard match `http://localhost:3000/api/auth/callback`
3. Ensure Auth0 Management API is authorized with `read:user_idp_tokens` scope

---

## 📚 Documentation

For detailed setup instructions, see [SETUP_GUIDE.md](./SETUP_GUIDE.md).

---

## 📝 License

This project is part of the Auth0 Hackathon.

---

## 🤝 Contributing

Contributions welcome! Please open issues or PRs for bug fixes and features.

---

## ❓ Support

- 📖 [Auth0 Documentation](https://auth0.com/docs)
- 🐍 [FastAPI Docs](https://fastapi.tiangolo.com)
- ⚛️ [Next.js Docs](https://nextjs.org/docs)
- 🔗 [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
