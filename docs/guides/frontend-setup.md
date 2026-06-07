# Frontend Setup

This project uses a Vite + React SPA because the frontend is an internal tool that mainly needs fast iteration, authenticated app flows, and a clean connection to the FastAPI backend. We do not need the extra server-rendering, SEO, or full-stack routing features that Next.js is optimized for.

## Prerequisites

Requires Node.js v22+. If you are on Windows with a space in your username, nvm-windows will fail to switch versions. Use the direct Node.js installer from https://nodejs.org instead.

## Init (from empty `frontend/`)

```bash
cd frontend
bunx create-vite . --template react-ts
bun install
bun add react-router-dom @supabase/supabase-js
bun add -D tailwindcss @tailwindcss/vite
bunx --bun shadcn@latest init
```

> If `bunx shadcn@latest init` fails due to an `msw` postinstall error, use `bunx --bun shadcn@latest init` or install directly with `bun add shadcn && bunx shadcn init`.

## Run

```bash
cd frontend
bun install
bun dev
```

## Check

```bash
bun tsc --noEmit
bun lint
```