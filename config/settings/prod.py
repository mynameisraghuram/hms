# config/settings/prod.py

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "https://app.yourdomain.com",
    "https://admin.yourdomain.com",
]
CORS_ALLOW_CREDENTIALS = True

SIMPLE_JWT["AUTH_COOKIE_SECURE"] = True
SIMPLE_JWT["AUTH_COOKIE_SAMESITE"] = "Lax"  # keep Lax if same-site via subdomain strategy
