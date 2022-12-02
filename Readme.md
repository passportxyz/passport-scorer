
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

##Testing
### API

In the `./api` folder run (make sure your local virtual env is activated): 
```
coverage run --source='.' manage.py test
```
