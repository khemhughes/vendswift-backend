import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI(title="VendSwift Backend")

# ----- Database connection helper -----

def get_conn():
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", "5432"),
    )
    return conn


# ----- Pydantic models for API responses -----

class ProductOut(BaseModel):
    id: str          # SKU
    name: str
    description: Optional[str] = None
    price: float
    currency: str
    image_url: Optional[str] = None


class MachineProductsResponse(BaseModel):
    machine_id: str
    machine_name: str
    products: List[ProductOut]


@app.get("/health", summary="Health check")
def health_check():
    return {"status": "ok"}


@app.get("/machines/{machine_code}/products",
         response_model=MachineProductsResponse)
def get_machine_products(machine_code: str):
    """
    Returns machine info + list of products for the given machine_code.
    machine_code is the value in your QR code, e.g. 'M12'.
    """
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get machine info
            cur.execute(
                """
                SELECT id, code, name
                FROM machines
                WHERE code = %s AND is_active = TRUE
                """,
                (machine_code,),
            )
            machine = cur.fetchone()
            if not machine:
                raise HTTPException(status_code=404, detail="Machine not found")

            machine_id_db = machine["id"]
            code = machine["code"]
            name = machine["name"]

            # Get products for machine
            cur.execute(
                """
                SELECT p.sku, p.name, p.description,
                       mp.price, mp.currency, p.image_url
                FROM machine_products mp
                JOIN products p ON p.id = mp.product_id
                WHERE mp.machine_id = %s AND mp.is_active = TRUE
                ORDER BY p.name;
                """,
                (machine_id_db,),
            )
            rows = cur.fetchall()

        products = [
            ProductOut(
                id=row["sku"],
                name=row["name"],
                description=row["description"],
                price=float(row["price"]),
                currency=row["currency"],
                image_url=row["image_url"],
            )
            for row in rows
        ]

        return MachineProductsResponse(
            machine_id=code,
            machine_name=name,
            products=products
        )

    finally:
        conn.close()
