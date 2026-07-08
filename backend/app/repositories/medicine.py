from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.medicine import Medicine
from app.utils.medicine_search import normalize_medicine_text


class MedicineRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_medicines(self, skip: int = 0, limit: int = 100) -> list[Medicine]:
        stmt = select(Medicine).offset(skip).limit(limit).order_by(Medicine.name.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_medicine_search_pool(self, limit: int = 500) -> list[Medicine]:
        stmt = select(Medicine).order_by(Medicine.name.asc()).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_medicine_candidates(self, query: str, limit: int = 25) -> list[Medicine]:
        normalized_query = normalize_medicine_text(query)
        if not normalized_query:
            return []

        pattern = f"%{normalized_query}%"
        stmt = (
            select(Medicine)
            .where(
                or_(
                    func.lower(Medicine.name).like(pattern),
                    func.lower(Medicine.generic_name).like(pattern),
                    func.lower(Medicine.salt_composition).like(pattern),
                )
            )
            .order_by(
                Medicine.is_generic.desc(),
                Medicine.price.asc(),
                Medicine.name.asc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name(self, medicine_name: str) -> Medicine | None:
        normalized_name = normalize_medicine_text(medicine_name)
        stmt: Select[tuple[Medicine]] = select(Medicine).where(func.lower(Medicine.name) == normalized_name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_alternatives(
        self,
        source_medicine: Medicine,
        generic_preference: bool = True,
        limit: int = 10,
    ) -> list[Medicine]:
        stmt = (
            select(Medicine)
            .where(Medicine.id != source_medicine.id)
            .where(Medicine.salt_composition == source_medicine.salt_composition)
            .where(Medicine.dosage == source_medicine.dosage)
            .where(Medicine.approval_status == "approved")
            .where(Medicine.price < source_medicine.price)
        )

        if generic_preference:
            stmt = stmt.order_by(
                Medicine.is_generic.desc(),
                Medicine.price.asc(),
                Medicine.name.asc(),
            )
        else:
            stmt = stmt.order_by(Medicine.price.asc(), Medicine.name.asc())

        result = await self.session.execute(stmt.limit(limit))
        return list(result.scalars().all())
