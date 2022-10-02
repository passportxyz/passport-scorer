
Start like: `gunicorn scorer.asgi:application  -k uvicorn.workers.UvicornWorker`

or `uvicorn scorer.asgi:application  --reload`
