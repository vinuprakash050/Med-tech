import asyncio
import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.models.medicine import Medicine

DATA_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "medicines.json"


def _load_seed_medicines() -> list[dict]:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    medicines = payload.get("medicines", [])
    if not isinstance(medicines, list):
        raise ValueError("medicines.json must contain a top-level 'medicines' array")
    return medicines


async def seed() -> None:
    seed_medicines = _load_seed_medicines()
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Medicine))
        session.add_all(
            [
                Medicine(
                    **{
                        **payload,
                        "price": Decimal(str(payload["price"])),
                    }
                )
                for payload in seed_medicines
            ]
        )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
