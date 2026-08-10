# EventIQ Log Analyzer

EventIQ analyzes Windows Event Log text, screenshots, XML files, and EVTX files. It stores analysis history, searches for references, and can export a Markdown report for sharing.

## Local Setup

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload
```

The API runs at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

The app runs at `http://localhost:3000`.

Default development login:

- Username: `admin`
- Password: `P@ssw0rd`

Change `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `JWT_SECRET` before deploying.

## OCR Setup On Windows

Image upload uses `pytesseract`, which requires the Tesseract desktop program.

1. Install Tesseract from the Windows installer: `https://github.com/UB-Mannheim/tesseract/wiki`
2. During install, include English and Thai language packs if you need Thai screenshots.
3. Add the Tesseract install folder to `PATH`, usually `C:\Program Files\Tesseract-OCR`.
4. Restart the backend terminal.
5. Test image upload from the Image tab.

If OCR fails, the backend returns a message with the Tesseract installer link.

## EVTX Upload

The File tab accepts `.evtx` and `.xml`. EVTX parsing uses `python-evtx`; the backend scans up to 100 records and picks the first Error/Critical event when possible.

## Docker Backend

The backend Docker image installs Tesseract OCR with English and Thai language packs, so image OCR works in Linux deployments.

Build and run only the backend:

```bash
cd backend
docker build -t eventiq-backend .
docker run --rm -p 8000:8000 \
  -e ADMIN_USERNAME=admin \
  -e ADMIN_PASSWORD=P@ssw0rd \
  -e JWT_SECRET=change-this \
  -e CORS_ORIGINS=http://localhost:3000 \
  eventiq-backend
```

Run backend plus Postgres locally:

```bash
docker compose up --build
```

The frontend can still run with:

```bash
cd frontend
npm run dev
```

## Markdown Export

Open any analysis result and click `Export Markdown`. The browser downloads a `.md` report containing metadata, summary, steps, and references.

## Deploy: Fly.io Backend

Fly.io is a good fit for this backend if you want Docker-first deployment and a real Linux runtime for Tesseract OCR.

1. Install and log in to `flyctl`.
2. Go to the backend folder:

```bash
cd backend
```

3. Create a Fly app and generate config:

```bash
fly launch
```

You can use `fly.toml.example` as a starting point. Change the `app` name to a globally unique Fly app name.

4. Add secrets:

```bash
fly secrets set ADMIN_USERNAME=admin
fly secrets set ADMIN_PASSWORD=your-strong-password
fly secrets set JWT_SECRET=your-long-random-secret
fly secrets set CORS_ORIGINS=https://your-vercel-app.vercel.app
```

5. Add Postgres if you want persistent history:

```bash
fly postgres create
fly postgres attach <postgres-app-name>
```

6. Deploy:

```bash
fly deploy
```

7. Check the API:

```bash
fly open /docs
```

## Deploy: Railway Backend

1. Create a Railway project from this repository.
2. Set the service root to `backend`.
3. Add environment variables:
   - `ADMIN_USERNAME`
   - `ADMIN_PASSWORD`
   - `JWT_SECRET`
   - `JWT_EXPIRE_HOURS`
   - `CORS_ORIGINS=https://your-vercel-app.vercel.app`
   - `DATABASE_URL` if using Railway Postgres
4. Railway can use `backend/Procfile`:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

5. After deploy, open `/docs` on the Railway URL to confirm the API is live.

## Deploy: Vercel Frontend

1. Import the repository in Vercel.
2. Set the project root to `frontend`.
3. Add environment variable:
   - `NEXT_PUBLIC_API_URL=https://your-railway-api.up.railway.app`
4. Deploy.
5. In Railway, set `CORS_ORIGINS` to the final Vercel domain and redeploy the backend.

## Phase 3 Status

- EVTX parser: implemented.
- OCR setup guide: documented.
- Export Markdown: implemented.
- Backend JWT auth: implemented and wired to frontend.
- Railway + Vercel deployment: documented with required config.
