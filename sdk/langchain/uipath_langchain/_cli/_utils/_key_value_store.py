import json

import aiosqlite


class SimpleKeyValueStore:
    def __init__(self):
        self.db = None

    async def init_db(self, connstring):
        self.db = await aiosqlite.connect(connstring)
        await self.db.execute(
            "CREATE TABLE IF NOT EXISTS uipath_simple_store (key TEXT PRIMARY KEY, value TEXT)"
        )

    async def get(self, key):
        cursor = await self.db.execute(
            "SELECT value FROM uipath_simple_store WHERE key=?", (key,)
        )
        row = await cursor.fetchone()
        return row[0] if row is not None else None

    async def get_json(self, key):
        row = self.get(key)
        return json.loads(row) if row is not None else None

    async def set(self, key, value):
        await self.db.execute(
            "INSERT OR REPLACE INTO uipath_simple_store (key, value) VALUES (?, ?)",
            (key, value),
        )
        await self.db.commit()

    async def close_db(self):
        await self.db.close()
