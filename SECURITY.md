# Security Policy

## Secrets

Never commit:

- VLM or LLM API keys
- Feishu webhook URLs or signing secrets
- private inspection videos
- model weights
- generated evidence screenshots
- local database files

`.gitignore` excludes `.env`, `data/`, `models/`, logs, local databases, and temporary evidence files.

## Reporting Security Issues

If you find a security issue, please open a private report through GitHub Security Advisories when available. If not available, open an issue with minimal reproduction details and avoid posting secrets or private videos.

## Runtime Notes

- Feishu webhook signing is supported.
- JWT is used by the API gateway and services.
- The demo defaults are for local development; change `SECRET_KEY`, database credentials, MinIO credentials, and default admin password before any real deployment.

## Safety Disclaimer

The project assists safety inspection workflows but does not replace qualified safety supervisors, site procedures, or certified safety systems.
