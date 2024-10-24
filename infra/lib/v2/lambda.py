import json
from gerald import get_msg


def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"msg": get_msg()}),
    }
