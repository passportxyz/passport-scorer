
# Getting Started

Create virtual env and install dependencies: `pipenv install`

Start the dev server:
- `gunicorn -w 4 -k uvicorn.workers.UvicornWorker scorer.asgi:application`
- or `uvicorn scorer.asgi:application --reload`
