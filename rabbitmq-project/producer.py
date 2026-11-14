
import json
import time
import random
import uuid
import logging

import pika

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PRODUCER] %(message)s"
)

RABBITMQ_HOST = "rabbitmq"
RABBITMQ_USER = "appuser"
RABBITMQ_PASSWORD = "apppass"


def connect():
    while True:
        try:
            credentials = pika.PlainCredentials(
                RABBITMQ_USER,
                RABBITMQ_PASSWORD
            )

            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    credentials=credentials
                )
            )

            logging.info("Connected to RabbitMQ")
            return connection

        except pika.exceptions.AMQPConnectionError:
            logging.info("Waiting for RabbitMQ...")
            time.sleep(3)


connection = connect()
channel = connection.channel()

# Создаём Direct Exchange
channel.exchange_declare(
    exchange="calculations",
    exchange_type="direct",
    durable=True
)

# Создаём Dead Letter Exchange
channel.exchange_declare(
    exchange="calculations.dlx",
    exchange_type="direct",
    durable=True
)

# Создаём очередь для ошибочных сообщений
channel.queue_declare(
    queue="calculations.dlq",
    durable=True
)

channel.queue_bind(
    exchange="calculations.dlx",
    queue="calculations.dlq",
    routing_key="failed"
)

# Создаём очереди для операций
operations = ["add", "subtract", "multiply", "divide"]

for operation in operations:
    queue_name = f"calculations.{operation}"

    channel.queue_declare(
        queue=queue_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "calculations.dlx",
            "x-dead-letter-routing-key": "failed"
        }
    )

    channel.queue_bind(
        exchange="calculations",
        queue=queue_name,
        routing_key=f"calc.{operation}"
    )

logging.info("Queues and exchanges configured")

counter = 0

while True:
    operation = random.choice(operations)

    a = random.randint(1, 100)
    b = random.randint(1, 100)

    counter += 1

    # Периодически создаём ошибку деления на ноль
    if operation == "divide" and random.random() < 0.8:
        b = 0

    message = {
        "id": str(uuid.uuid4()),
        "operation": operation,
        "a": a,
        "b": b
    }

    routing_key = f"calc.{operation}"

    channel.basic_publish(
        exchange="calculations",
        routing_key=routing_key,
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2,
            content_type="application/json"
        )
    )

    logging.info(
        f"Sent message: {message}, routing_key={routing_key}"
    )

    time.sleep(5)

