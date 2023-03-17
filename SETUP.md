# Setup

## Getting Started

The Scorer API has a couple of key components to it, the API and interface being
the main two for you to set up:

```shell
.
├── api/        # Django API powering the interface and API
├── examples/   # Set of examples for working with the API
├── infra/      # Deployment infrastructure for hosting the API
├── interface/  # React-based user interface
└── test/       # End-to-end tests
```

## API

A [`Dockerfile`](./api/Dockerfile) has been provided to quickly get the API
environment up and running. Setup instructions are also provided below.

### With Docker

1. Create a new `.env` file by copying the existing `.env-sample` file

```shell
# From inside the api/ directory
cp .env-example .env
```

2. Run and build the `Dockerfile`. The first time you run this, it will take
   a while to build the Docker images.
```
cd api
docker-compose up --build
```

The API will be running on port 8000 and the database will be running on port
5432.

### Without docker

We assume that you have a working python environment set up on your machine with
the following:

- A recent version of Python
- `pipenv`

The following commands should be run from within the `api/` directory.

1. Activate your local virtual environment:

```
pipenv shell
```

2. Install dependencies in your virtual environment:

```
pipenv install
pipenv install --dev
```

3. Start the dev server:

**First**: make sure you have the `.env` file in the api folder, with proper
values (copy the `.env-sample` and adjust it). Then:

```shell
gunicorn -b 127.0.0.1:8002 -w 4 -k uvicorn.workers.UvicornWorker scorer.asgi:application
```

or:

```shell
uvicorn scorer.asgi:application --reload --port 8002
```

Start the celery worker:

```shell
celery -A scorer worker -l DEBUG
```

And run Redis locally:

```shell
docker run -d -p 6379:6379 redis
```

> Make sure you have Docker running

## Interface

The front end is built using Next.js and is using a fairly standard installation
without much customization.

To run the front end, change into the `interface/` directory and install the
dependencies:
```
yarn
```

Copy the `.env.example` file:

```shell
cp .env.example .env
```

You will need an [Alchemy API key](https://docs.alchemy.com/reference/api-overview).

To start the development server:

```
yarn dev
```

## Testing

### API

> The following assumes you are in the api/ directory and that you've already
activated your local virtual environment

In the `./api` directory run (make sure your local virtual env is activated):

```
coverage run --source='.' manage.py test
```

#### pytest

> The following assumes you are in the api/ directory

We use pytest to run tests. In `./api` folder run:

```shell
pytest
```

#### bdd

> The following assumes you are in the api/ directory

- **docs**:
  - [pytest-bdd](https://pytest-bdd.readthedocs.io/en/latest/#advanced-code-generation)
  - https://automationpanda.com/2018/10/22/python-testing-101-pytest-bdd/
  - examples: https://github.com/AndyLPK247/behavior-driven-python
  - https://github.com/pytest-dev/pytest-mock
- **Location of feature file:**: ./api/account/test/features
- **cmd to generate missing code:** (run from `./api` and virtulanv): `pytest --generate-missing --feature scorer/test/features scorer/test`
  - you will need to copy & paste the code from terminal to `test_.*.py` file

### Cypress

> The following assumes you are in the test/ directory

1. Install dependencies with yarn:

```shell
yarn
```

2. Run Cypress tests:

```shell
yarn cypress run
```

3. Open Cypress:

```shell
yarn cypress open
```
