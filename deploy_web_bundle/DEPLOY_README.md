# Deploy Web Bundle

This folder is a deploy-ready package for your Streamlit web app.

## Contents
- streamlit_app.py
- requirements.txt
- .env.example
- .streamlit/config.toml
- Procfile (for Render/Heroku-style platforms)
- start.sh (Linux startup)
- Dockerfile (generic container hosting)

## 1) Set environment variables in hosting
Use values from your Oracle setup. Do not upload secrets in files.

Required variables:
- ORACLE_HOST
- ORACLE_PORT
- ORACLE_SERVICE
- ORACLE_USER
- ORACLE_PASSWORD

Optional variables:
- APP_AUTH_MODE (oracle or app)
- APP_LOGIN_USER
- APP_LOGIN_PASSWORD

## 2) Deploy option A: Buildpack/Native Python hosting
Start command:

streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0

If your host supports Procfile, it will use:

web: streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0

## 3) Deploy option B: Docker hosting
Build and run:

```bash
docker build -t oracle-workbench .
docker run -p 8501:8501 --env-file .env oracle-workbench
```

## 4) Local quick test from this folder

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

Open:
- http://localhost:8501

## Notes
- Keep .env out of git and out of public uploads.
- Ensure your hosting network can reach the Oracle host and port.
