import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models import Submission

async def main():
    async with AsyncSessionLocal() as session:
        stmt = select(Submission).order_by(Submission.uploaded_at.desc()).limit(1)
        res = await session.execute(stmt)
        sub = res.scalar_one_or_none()
        if sub:
            print(f'ID: {sub.id}, file: {sub.file_name}, status: {sub.status}')
            print(f'summary keys: {list(sub.summary.keys()) if isinstance(sub.summary, dict) else sub.summary}')
        else:
            print('No submissions found')

if __name__ == "__main__":
    asyncio.run(main())
