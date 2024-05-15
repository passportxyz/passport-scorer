# https://pipenv.pypa.io/en/latest/basics/#pipenv-and-docker-containers
FROM --platform=linux/amd64 python

# Set arguments with default values
ARG TEST_DURATION="5s"
ARG VIRTUAL_USERS="1"

ADD . /load_tests

# k6 installation guide: https://grafana.com/docs/k6/latest/set-up/install-k6/
RUN gpg -k
RUN gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
RUN echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | tee /etc/apt/sources.list.d/k6.list

RUN apt update
RUN apt install -y nodejs npm pipenv k6

WORKDIR /load_tests/generate_test_auth_tokens
RUN npm install

WORKDIR /load_tests/test_data
RUN pipenv install

WORKDIR /load_tests

CMD ["./run_scorer_load_test.sh", "${VIRTUAL_USERS}", "${TEST_DURATION}"]
