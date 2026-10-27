"""A typical FastAPI service: every dependency is imported at the top, but most
endpoints only need a few of them."""
import os
from datetime import datetime, timezone

import boto3
import httpx
import pandas as pd
from fastapi import FastAPI, HTTPException
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy import Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool

# One shared in-memory database across threads (the usual FastAPI + SQLite test setup).
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))


Base.metadata.create_all(engine)


class ItemIn(BaseModel):
    name: str


app = FastAPI()


@app.get("/health")
def health():
    return {"ok": True, "time": datetime.now(timezone.utc).isoformat()}


@app.post("/items")
def create_item(item: ItemIn):
    with Session(engine) as s:
        row = Item(name=item.name)
        s.add(row)
        s.commit()
        return {"id": row.id, "name": row.name}


@app.get("/items")
def list_items():
    with Session(engine) as s:
        return [{"id": i.id, "name": i.name} for i in s.scalars(select(Item))]


@app.get("/report")
def report():
    with Session(engine) as s:
        df = pd.DataFrame([{"name": i.name} for i in s.scalars(select(Item))])
    return {"rows": len(df)}


@app.post("/upload")
def upload():
    s3 = boto3.client("s3", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x")
    return {"bucket_client": type(s3).__name__}


@app.post("/ask")
def ask():
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "sk-test"))
    return {"client": type(client).__name__}


@app.get("/proxy")
def proxy():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))
    with httpx.Client(transport=transport) as c:
        r = c.get("https://example.com")
    if r.status_code != 200:
        raise HTTPException(502)
    return r.json()
