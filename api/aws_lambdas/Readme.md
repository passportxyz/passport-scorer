# Testing the Application Locally with Docker

## 1. Building the Docker Image

First, navigate to the passport-scorer root directory. Then, execute the command below to build the Docker image:

```bash
docker build --platform linux/amd64 -t docker-image:test -f ./api/aws_lambdas/submit_passport/Dockerfile ./api
```

## 2. Running the Docker Image

Once you've successfully built the image, you can run it. Ensure you point to the location of your running PostgreSQL instance. In this context, the database is running in another Docker container:

```bash
docker run -e DATABASE_URL=postgres://passport_scorer:passport_scorer_pwd@host.docker.internal:5432/passport_scorer -p 8080:8080 docker-image:test
```

### 3. Making Curl Requests

After you have your application up and running, you can test its endpoints using `curl`. Use the command below to make a request to the instance:

````markdown
```bash
curl -X 'POST' \
  'http://localhost:8080/2015-03-31/functions/function/invocations' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "requestContext": {
    "elb": {
      "targetGroupArn": "arn"
    }
  },
  "httpMethod": "POST",
  "path": "/registry/submit-passport",
  "queryStringParameters": {},
  "headers": {add necessary headers here},
  "body": "{\"address\":\"0x868asAe3B27asdF475e41FAdDF9F0cf97fDB71fC\",\"community\":\"24\"}",
  "isBase64Encoded": false
}'
```
