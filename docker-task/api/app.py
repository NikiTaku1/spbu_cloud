import os
import time

import psycopg2
from flask import Flask, jsonify, request

app = Flask(__name__)

DB_CONFIG = dict(
    host=os.getenv("DB_HOST", "db"),
    port=os.getenv("DB_PORT", "5432"),
    dbname=os.getenv("DB_NAME", "appdb"),
    user=os.getenv("DB_USER", "appuser"),
    password=os.getenv("DB_PASSWORD", "apppass"),
)


def get_conn(retries=10, delay=2):
    for attempt in range(retries):
        try:
            return psycopg2.connect(**DB_CONFIG)
        except psycopg2.OperationalError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def query(sql, params=None):
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else None
    finally:
        conn.close()


def to_dict(row):
    return {"id": row[0], "name": row[1], "created_at": row[2].isoformat()}


@app.get("/health")
def health():
    query("SELECT 1")
    return jsonify(status="ok")


@app.get("/items")
def list_items():
    rows = query("SELECT id, name, created_at FROM items ORDER BY id")
    return jsonify([to_dict(r) for r in rows])


@app.post("/items")
def add_item():
    data = request.get_json(force=True)
    name = (data or {}).get("name")
    if not name:
        return jsonify(error="field 'name' is required"), 400
    row = query(
        "INSERT INTO items (name) VALUES (%s) RETURNING id, name, created_at",
        (name,),
    )[0]
    return jsonify(to_dict(row)), 201
