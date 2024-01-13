
# https://pipenv.pypa.io/en/latest/basics/#pipenv-and-docker-containers
FROM public.ecr.aws/lambda/python:3.11 AS base


#########################################################
# Builder
#########################################################
FROM base AS builder

RUN pip install pipenv

# Tell pipenv to create venv in the current directory
ENV PIPENV_VENV_IN_PROJECT=1

ADD Pipfile.lock /usr/src/

WORKDIR /usr/src

RUN pipenv requirements > requirements.txt

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
