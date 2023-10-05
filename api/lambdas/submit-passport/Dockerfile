
# https://pipenv.pypa.io/en/latest/basics/#pipenv-and-docker-containers
FROM public.ecr.aws/lambda/python:3.11 AS base


#########################################################
# Builder
#########################################################
FROM base AS builder

RUN pip install --user pipenv

# Tell pipenv to create venv in the current directory
ENV PIPENV_VENV_IN_PROJECT=1

ADD Pipfile.lock /usr/src/

WORKDIR /usr/src


# NOTE: If you install binary packages required for a python module, you need
# to install them again in the runtime. For example, if you need to install pycurl
# you need to have pycurl build dependencies libcurl4-gnutls-dev and libcurl3-gnutls
# In the runtime container you need only libcurl3-gnutls

# RUN apt install -y libcurl3-gnutls libcurl4-gnutls-dev
# RUN /root/.local/bin/pipenv lock
ADD Pipfile /usr/src/
ADD Pipfile.lock /usr/src/

RUN /root/.local/bin/pipenv run pip freeze > requirements.txt

RUN cat requirements.txt
# RUN /usr/src/.venv/bin/python -c "import django; print(django.__version__)"
RUN ls /usr/src/.venv/lib/

#########################################################
# Runtime
#########################################################
FROM base AS runtime

# RUN mkdir -v /usr/src/venv

COPY --from=builder /usr/src/requirements.txt ${LAMBDA_TASK_ROOT}
COPY ./ ${LAMBDA_TASK_ROOT}


WORKDIR ${LAMBDA_TASK_ROOT}

RUN cat requirements.txt
RUN pip install -r requirements.txt
# RUN pip install Django

RUN python -c "import django; print(f\"\n{'*' * 40}\n* DJANGO VERSION: {django.__version__ : <21}*\n{'*' * 40}\n\")"
# ENV PATH="/usr/src/.venv/bin/:${PATH}"


RUN STATIC_ROOT=${LAMBDA_TASK_ROOT}/static SECRET_KEY=secret_is_irelevent_here CERAMIC_CACHE_SCORER_ID=1 DATABASE_URL=sqlite:////dunmmy_db.sqlite3 python manage.py collectstatic --noinput

CMD [ "submit_passport.handler" ]
