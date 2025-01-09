
# https://pipenv.pypa.io/en/latest/basics/#pipenv-and-docker-containers
FROM --platform=linux/amd64 public.ecr.aws/lambda/python:3.12 AS base


#########################################################
# Builder
#########################################################
FROM base AS builder

# Installing the poetry export plugin as per instructions here: https://github.com/python-poetry/poetry-plugin-export?tab=readme-ov-file#installation
#   - Note: using `pipx inject poetry poetry-plugin-export` did not work in this case for unknown reasons
RUN  pip install --upgrade pip && \
    pip install --user pipx && \
    /root/.local/bin/pipx ensurepath && \
    /root/.local/bin/pipx install poetry && \
    /root/.local/bin/poetry self add poetry-plugin-export

# Tell pipenv to create venv in the current directory
ENV POETRY_VIRTUALENVS_IN_PROJECT=1

ADD poetry.lock /usr/src/
ADD pyproject.toml /usr/src/

WORKDIR /usr/src

RUN /root/.local/bin/poetry export --with server --without dev -f requirements.txt -o requirements.txt

#########################################################
# Runtime
#########################################################
FROM base AS runtime

COPY --from=builder /usr/src/requirements.txt ${LAMBDA_TASK_ROOT}
COPY ./ ${LAMBDA_TASK_ROOT}


WORKDIR ${LAMBDA_TASK_ROOT}

RUN pip install -r requirements.txt

RUN python -c "import django; print(f\"\n{'*' * 40}\n* DJANGO VERSION: {django.__version__ : <21}*\n{'*' * 40}\n\")"


RUN STATIC_ROOT=${LAMBDA_TASK_ROOT}/static SECRET_KEY=secret_is_irelevent_here CERAMIC_CACHE_SCORER_ID=1 DATABASE_URL=sqlite:////dunmmy_db.sqlite3 python manage.py collectstatic --noinput

CMD [ "aws_lambdas.submit_passport.submit_passport.handler" ]
