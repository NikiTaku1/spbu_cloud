
import json
import logging
import os
import time

import pika

RABBITMQ_HOST = "rabbitmq"
RABBITMQ_USER = "appuser"
RABBITMQ_PASSWORD = "apppass"

OPERATIONS = ["add", "subtract", "multiply", "divide"]

# Создаём папку для логов
os.makedirs("logs", exist_ok=True)

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CONSUMER] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/consumer.log"),
        logging.StreamHandler()
    ]
)


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


def calculate(operation, a, b):

    if operation == "add":
        return a + b

    elif operation == "subtract":
        return a - b

    elif operation == "multiply":
        return a * b

    elif operation == "divide":
        if b == 0:
            raise ValueError("Division by zero")

        return a / b

    else:
        raise ValueError(f"Unknown operation: {operation}")


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

# Создаём Dead Letter Queue
channel.queue_declare(
    queue="calculations.dlq",
    durable=True
)

channel.queue_bind(
    exchange="calculations.dlx",
    queue="calculations.dlq",
    routing_key="failed"
)

# Создаём очереди и привязки
for operation in OPERATIONS:

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


def callback(ch, method, properties, body):

    try:
        message = json.loads(body.decode("utf-8"))

        operation = message["operation"]
        a = message["a"]
        b = message["b"]

        if operation not in OPERATIONS:
            raise ValueError("Unsupported operation")

        if (
            isinstance(a, bool)
            or not isinstance(a, (int, float))
            or isinstance(b, bool)
            or not isinstance(b, (int, float))
        ):
            raise ValueError("Invalid numbers")

        result = calculate(operation, a, b)

        logging.info(
            f"SUCCESS | {a} {operation} {b} = {result} "
            f"| message_id={message.get('id')}"
        )

        # Подтверждаем успешную обработку
        ch.basic_ack(
            delivery_tag=method.delivery_tag
        )

    except Exception as error:

        logging.error(
            f"FAILED | Error: {error} | Message: {body}"
        )

        # Отправляем ошибочное сообщение в DLQ
        ch.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=False
        )


# Ограничиваем количество неподтверждённых сообщений
channel.basic_qos(prefetch_count=1)

# Подписываемся на все очереди
for operation in OPERATIONS:

    queue_name = f"calculations.{operation}"

    channel.basic_consume(
        queue=queue_name,
        on_message_callback=callback
    )

logging.info("Consumer started")
logging.info("Waiting for messages...")

channel.start_consuming()

