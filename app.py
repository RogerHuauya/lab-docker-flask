import os
from flask import Flask, jsonify, request, abort
from psycopg_pool import ConnectionPool

app = Flask(__name__)


def _read_secret(path, env_fallback=None):
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    return os.environ.get(env_fallback, "")


def _conninfo():
    host = os.environ.get("DB_HOST", "db")
    port = os.environ.get("DB_PORT", "5432")
    dbname = os.environ.get("DB_NAME", "itemsdb")
    user = os.environ.get("DB_USER", "flask_user")
    password = _read_secret("/run/secrets/pg_password", "DB_PASSWORD")
    return f"host={host} port={port} dbname={dbname} user={user} password={password}"


pool = ConnectionPool(conninfo=_conninfo(), min_size=1, max_size=10)


def _row_to_dict(row):
    return {
        "id": row[0],
        "name": row[1],
        "description": row[2],
        "created_at": row[3].isoformat(),
    }


@app.get("/api/health")
def health():
    return jsonify({"status": "healthy", "message": "Flask + PostgreSQL funcionando"})


@app.get("/api/items")
def list_items():
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT id, name, description, created_at FROM items ORDER BY id"
        ).fetchall()
    return jsonify([_row_to_dict(r) for r in rows])


@app.post("/api/items")
def create_item():
    data = request.get_json(force=True) or {}
    name = data.get("name", "").strip()
    if not name:
        abort(400, description="El campo 'name' es requerido")
    description = data.get("description", "")
    with pool.connection() as conn:
        row = conn.execute(
            "INSERT INTO items (name, description) VALUES (%s, %s)"
            " RETURNING id, name, description, created_at",
            (name, description),
        ).fetchone()
    return jsonify(_row_to_dict(row)), 201


@app.get("/api/items/<int:item_id>")
def get_item(item_id):
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT id, name, description, created_at FROM items WHERE id = %s",
            (item_id,),
        ).fetchone()
    if row is None:
        abort(404, description="Item no encontrado")
    return jsonify(_row_to_dict(row))


@app.put("/api/items/<int:item_id>")
def update_item(item_id):
    data = request.get_json(force=True) or {}
    name = data.get("name", "").strip()
    if not name:
        abort(400, description="El campo 'name' es requerido")
    description = data.get("description", "")
    with pool.connection() as conn:
        row = conn.execute(
            "UPDATE items SET name = %s, description = %s WHERE id = %s"
            " RETURNING id, name, description, created_at",
            (name, description, item_id),
        ).fetchone()
    if row is None:
        abort(404, description="Item no encontrado")
    return jsonify(_row_to_dict(row))


@app.delete("/api/items/<int:item_id>")
def delete_item(item_id):
    with pool.connection() as conn:
        result = conn.execute(
            "DELETE FROM items WHERE id = %s RETURNING id", (item_id,)
        ).fetchone()
    if result is None:
        abort(404, description="Item no encontrado")
    return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
