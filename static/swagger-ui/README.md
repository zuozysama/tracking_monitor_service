Offline Swagger UI assets

Why this folder may only contain README in source tree:

- We do not commit third-party Swagger UI binaries into git by default.
- During Docker build, `scripts/prepare_swagger_assets.py` tries to copy files
  from installed `swagger-ui-bundle` package into this folder automatically.

Required files:

- swagger-ui-bundle.js
- swagger-ui.css
- favicon-32x32.png (optional)

Expected URL path mapping after container startup:

- /assets/swagger-ui/swagger-ui-bundle.js
- /assets/swagger-ui/swagger-ui.css
- /assets/swagger-ui/favicon-32x32.png

Notes:

- This project serves `/api/swagger_ui/index.html` without internet when local assets exist.
- If local assets are missing, the service returns an offline hint page and keeps `/api/swagger.json` available.
