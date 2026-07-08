import asyncio
from decimal import Decimal

from sqlalchemy import delete

from app.core.database import AsyncSessionLocal
from app.models.medicine import Medicine


SEED_MEDICINES = [
    {
        "name": "Dolo 650",
        "salt_composition": "Paracetamol",
        "dosage": "650mg",
        "manufacturer": "Micro Labs",
        "medicine_type": "tablet",
        "price": Decimal("35.00"),
        "is_generic": False,
        "approval_status": "approved",
        "description": "Used for fever and mild pain relief.",
        "common_side_effects": "nausea,drowsiness,headache",
        "allergy_warnings": "avoid if allergic to paracetamol",
        "precautions": "consult doctor if pregnant",
    },
    {
        "name": "Pacimol 650",
        "salt_composition": "Paracetamol",
        "dosage": "650mg",
        "manufacturer": "Ipca Laboratories",
        "medicine_type": "tablet",
        "price": Decimal("18.00"),
        "is_generic": True,
        "approval_status": "approved",
        "description": "Generic paracetamol tablet for pain and fever.",
        "common_side_effects": "nausea,drowsiness,headache",
        "allergy_warnings": "avoid if allergic to paracetamol",
        "precautions": "consult doctor if pregnant",
    },
    {
        "name": "Crocin 650",
        "salt_composition": "Paracetamol",
        "dosage": "650mg",
        "manufacturer": "GSK",
        "medicine_type": "tablet",
        "price": Decimal("24.00"),
        "is_generic": False,
        "approval_status": "approved",
        "description": "Paracetamol-based fever reducer.",
        "common_side_effects": "nausea,drowsiness,headache",
        "allergy_warnings": "avoid if allergic to paracetamol",
        "precautions": "consult doctor if pregnant",
    },
    {
        "name": "Calpol 650",
        "salt_composition": "Paracetamol",
        "dosage": "650mg",
        "manufacturer": "GSK",
        "medicine_type": "tablet",
        "price": Decimal("30.00"),
        "is_generic": False,
        "approval_status": "approved",
        "description": "Paracetamol tablet indicated for fever.",
        "common_side_effects": "nausea,drowsiness,headache",
        "allergy_warnings": "avoid if allergic to paracetamol",
        "precautions": "consult doctor if pregnant",
    },
    {
        "name": "Azithromycin 500",
        "salt_composition": "Azithromycin",
        "dosage": "500mg",
        "manufacturer": "Sun Pharma",
        "medicine_type": "tablet",
        "price": Decimal("82.00"),
        "is_generic": False,
        "approval_status": "approved",
        "description": "Macrolide antibiotic.",
        "common_side_effects": "nausea,diarrhea,stomach upset",
        "allergy_warnings": "avoid if allergic to azithromycin or other macrolide antibiotics",
        "precautions": "consult doctor if you have liver problems",
    },
    {
        "name": "Azee 500",
        "salt_composition": "Azithromycin",
        "dosage": "500mg",
        "manufacturer": "Cipla",
        "medicine_type": "tablet",
        "price": Decimal("65.00"),
        "is_generic": True,
        "approval_status": "approved",
        "description": "Azithromycin generic alternative.",
        "common_side_effects": "nausea,diarrhea,stomach upset",
        "allergy_warnings": "avoid if allergic to azithromycin or other macrolide antibiotics",
        "precautions": "consult doctor if you have liver problems",
    },
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Medicine))
        session.add_all([Medicine(**payload) for payload in SEED_MEDICINES])
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
