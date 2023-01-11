
# Getting Started

## Interface
To run the frontend
```
cd interface
yarn
yarn dev
```

## API
### With Docker
```
cd api
docker compose up --build
```

### Without docker
Activate your local virtual env
```
pipenv shell
```

Create virtual env and install dependencies:
```
pipenv install
```

Start the dev server:
- **first**: make sure you have the `.env` file in the api folder, with proper values (clone the `.env-sample` if required and adjust it)
- `gunicorn -w 4 -k uvicorn.workers.UvicornWorker scorer.asgi:application`
- or `uvicorn scorer.asgi:application --reload`

Start the celery worker:
- `celery -A scorer worker -l DEBUG`

Running redis locally:

- `docker run -d -p 6379:6379 redis`

##Testing
### API

In the `./api` folder run (make sure your local virtual env is activated):
```
coverage run --source='.' manage.py test
```


#### pytest
- use pytest to run tests. In `./api` folder run `pytest`

#### bdd

Make sure you install the dev dependencies `pipenv install --dev`.

- **docs**:
  - [pytest-bdd](https://pytest-bdd.readthedocs.io/en/latest/#advanced-code-generation)
  - https://automationpanda.com/2018/10/22/python-testing-101-pytest-bdd/
  - examples: https://github.com/AndyLPK247/behavior-driven-python
  - https://github.com/pytest-dev/pytest-mock
- **Location of feature file:**: ./api/account/test/features
- **cmd to generate missing code:** (run from `./api` and virtulanv): `pytest --generate-missing --feature scorer/test/features scorer/test`
  - you will need to copy & paste the code from terminal to `test_.*.py` file



### Cypress

In the `./test`:
- exec cypress tests: `yarn cypress run`
- open cypress: `yarn cypress open`
