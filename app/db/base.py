from app.storage.local_store import init_stores


async def init_db():
    await init_stores()


async def get_db():
    yield None