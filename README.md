## Roles bootstrap (dev/staging/prod)

This project uses Django Groups as role identifiers for API permissions (e.g., Tasks workflow).

### 1) Ensure default role groups exist (idempotent)
```bash
python manage.py ensure_roles
