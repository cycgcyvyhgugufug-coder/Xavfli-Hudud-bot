import aiosqlite
import datetime

class Database:
    def __init__(self, db_path="bot.db"):
        self.db_path = db_path

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_path)
        await self.create_tables()

    async def create_tables(self):
        await self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                username TEXT,
                vip_until TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                cover_id TEXT,
                post_desc TEXT,
                main_desc TEXT,
                price INTEGER,
                views INTEGER DEFAULT 0
            );
            
            CREATE TABLE IF NOT EXISTS video_qualities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER,
                quality TEXT,
                file_id TEXT
            );
            
            CREATE TABLE IF NOT EXISTS purchases (
                user_id INTEGER,
                video_id INTEGER,
                PRIMARY KEY(user_id, video_id)
            );
            
            CREATE TABLE IF NOT EXISTS likes (
                user_id INTEGER,
                video_id INTEGER,
                is_like INTEGER,
                PRIMARY KEY(user_id, video_id)
            );
            CREATE TABLE IF NOT EXISTS video_views (
                user_id INTEGER,
                video_id INTEGER,
                viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, video_id)
            );
            
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            
            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                url TEXT,
                is_mandatory INTEGER
            );

            CREATE TABLE IF NOT EXISTS gift_campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                days INTEGER NOT NULL,
                tariff_name TEXT NOT NULL,
                max_winners INTEGER NOT NULL,
                claimed_count INTEGER NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                completed_notified INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS gift_claims (
                gift_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                claimed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (gift_id, user_id)
            );
        ''')
        await self.conn.commit()
        await self.conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('card', '8600 0000 0000 0000')")
        await self.conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_link', '@admin')")
        await self.conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('base_channel', '')")
        await self.conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('bot_info', 'Ushbu bot orqali siz turli sifatdagi (360p, 480p, 720p, 1080p) videolarni tomosha qilishingiz mumkin!\n\nSiz videolarni donalab sotib olishingiz yoki VIP tariflarni xarid qilib barcha videolarni cheklovsiz ko'rishingiz mumkin.\nDonalab olingan videolar doimiy sizning kabinetingizda qoladi.\nVIP tariflarida esa obuna tugagunga qadar barcha videolarni ko'rish huquqiga ega bo'lasiz.')")
        await self.conn.commit()

    async def add_user(self, user_id, name, username):
        await self.conn.execute(
            """INSERT INTO users (user_id, name, username) VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, username=excluded.username""",
            (user_id, name, username)
        )
        await self.conn.commit()

    async def get_user(self, user_id):
        async with self.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

    async def get_total_users(self):
        async with self.conn.execute("SELECT COUNT(*) FROM users") as cursor:
            return (await cursor.fetchone())[0]

    async def get_vip_users_count(self):
        now = datetime.datetime.now()
        async with self.conn.execute("SELECT COUNT(*) FROM users WHERE vip_until > ?", (now,)) as cursor:
            return (await cursor.fetchone())[0]

    async def set_vip(self, user_id, days):
        now = datetime.datetime.now()
        user = await self.get_user(user_id)
        current_until = None
        if user and user[3]:
            try:
                current_until = datetime.datetime.fromisoformat(str(user[3]))
            except (TypeError, ValueError):
                current_until = None
        base = current_until if current_until and current_until > now else now
        vip_until = base + datetime.timedelta(days=days)
        await self.conn.execute("UPDATE users SET vip_until = ? WHERE user_id = ?", (vip_until, user_id))
        await self.conn.commit()

    async def is_vip(self, user_id):
        user = await self.get_user(user_id)
        if user and user[3]:
            vip_until = datetime.datetime.fromisoformat(user[3])
            return vip_until > datetime.datetime.now()
        return False

    async def get_broadcast_users(self, target):
        now = datetime.datetime.now()
        if target == "vip":
            query = "SELECT user_id FROM users WHERE vip_until IS NOT NULL AND vip_until > ?"
        else:
            query = "SELECT user_id FROM users WHERE vip_until IS NULL OR vip_until <= ?"
        async with self.conn.execute(query, (now,)) as cursor:
            rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def get_non_vip_users(self):
        now = datetime.datetime.now()
        async with self.conn.execute(
            "SELECT user_id FROM users WHERE vip_until IS NULL OR vip_until <= ?",
            (now,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def create_gift_campaign(self, days, tariff_name, max_winners):
        async with self.conn.execute(
            "INSERT INTO gift_campaigns (days, tariff_name, max_winners) VALUES (?, ?, ?)",
            (days, tariff_name, max_winners)
        ) as cursor:
            gift_id = cursor.lastrowid
        await self.conn.commit()
        return gift_id

    async def claim_gift(self, gift_id, user_id):
        # Atomik claim: bir vaqtning o'zida ko'p odam bosganda limit oshib ketmaydi.
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            async with self.conn.execute(
                "SELECT id, days, tariff_name, max_winners, claimed_count, active, completed_notified FROM gift_campaigns WHERE id = ?",
                (gift_id,)
            ) as cur:
                gift = await cur.fetchone()
            if not gift:
                await self.conn.rollback(); return "full", gift

            # Avval aynan shu foydalanuvchi bu giftni olgan-olmaganini tekshiramiz.
            # Gift limiti tugaganidan keyin ham qayta bosganda "allaqachon oldingiz"
            # xabari chiqishi kerak.
            async with self.conn.execute("SELECT 1 FROM gift_claims WHERE gift_id=? AND user_id=?", (gift_id, user_id)) as cur:
                if await cur.fetchone():
                    await self.conn.rollback(); return "already", gift

            if gift[5] != 1:
                await self.conn.rollback(); return "full", gift

            async with self.conn.execute("SELECT vip_until FROM users WHERE user_id=?", (user_id,)) as cur:
                user = await cur.fetchone()
            if not user:
                await self.conn.rollback(); return "not_found", gift

            if user[0]:
                try:
                    if datetime.datetime.fromisoformat(str(user[0])) > datetime.datetime.now():
                        await self.conn.rollback(); return "vip", gift
                except (TypeError, ValueError):
                    pass

            new_count = gift[4] + 1
            if new_count > gift[3]:
                await self.conn.rollback(); return "full", gift

            await self.conn.execute("INSERT INTO gift_claims (gift_id,user_id) VALUES (?,?)", (gift_id,user_id))
            completed = new_count >= gift[3]
            await self.conn.execute(
                "UPDATE gift_campaigns SET claimed_count=?, active=?, completed_notified=? WHERE id=?",
                # completed_notified bu yerda o'zgarmaydi. Limit to'lgach claim
                # handler admin uchun bildirishnomani aynan bir marta yuboradi.
                (new_count, 0 if completed else 1, gift[6], gift_id)
            )
            await self.conn.commit()
            return "won", (gift[0], gift[1], gift[2], gift[3], new_count, 0 if completed else 1, 1 if completed else gift[6])
        except Exception:
            await self.conn.rollback()
            raise

    async def get_gift_winners(self, gift_id):
        async with self.conn.execute(
            "SELECT u.user_id, u.name, u.username FROM gift_claims g JOIN users u ON u.user_id=g.user_id WHERE g.gift_id=? ORDER BY g.claimed_at ASC",
            (gift_id,)
        ) as cur:
            return await cur.fetchall()

    async def mark_gift_completed_notified(self, gift_id):
        async with self.conn.execute(
            "UPDATE gift_campaigns SET completed_notified=1 WHERE id=? AND completed_notified=0",
            (gift_id,)
        ) as cur:
            changed=cur.rowcount
        await self.conn.commit()
        return changed == 1

    async def revoke_vip(self, user_id):
        user=await self.get_user(user_id)
        if not user:
            return "not_found"
        if not user[3]:
            return "no_vip"
        try:
            if datetime.datetime.fromisoformat(str(user[3])) <= datetime.datetime.now():
                return "no_vip"
        except (TypeError, ValueError):
            return "no_vip"
        await self.conn.execute("UPDATE users SET vip_until=NULL WHERE user_id=?", (user_id,))
        await self.conn.commit()
        return "revoked"

    async def add_video(self, code, cover_id, post_desc, main_desc, price):
        async with self.conn.execute("INSERT INTO videos (code, cover_id, post_desc, main_desc, price) VALUES (?, ?, ?, ?, ?)", (code, cover_id, post_desc, main_desc, price)) as cursor:
            video_id = cursor.lastrowid
            await self.conn.commit()
            return video_id

    async def add_video_quality(self, video_id, quality, file_id):
        await self.conn.execute("INSERT INTO video_qualities (video_id, quality, file_id) VALUES (?, ?, ?)", (video_id, quality, file_id))
        await self.conn.commit()

    async def get_video_by_code(self, code):
        async with self.conn.execute("SELECT * FROM videos WHERE code = ?", (code,)) as cursor:
            return await cursor.fetchone()

    async def get_video(self, video_id):
        async with self.conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)) as cursor:
            return await cursor.fetchone()

    async def get_video_qualities(self, video_id):
        async with self.conn.execute("SELECT quality, file_id FROM video_qualities WHERE video_id = ?", (video_id,)) as cursor:
            return await cursor.fetchall()

    async def get_video_quality_file(self, video_id, quality):
        async with self.conn.execute("SELECT file_id FROM video_qualities WHERE video_id = ? AND quality = ?", (video_id, quality)) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else None

    async def count_view_once(self, user_id, video_id):
        cursor = await self.conn.execute(
            "INSERT OR IGNORE INTO video_views (user_id, video_id) VALUES (?, ?)",
            (user_id, video_id)
        )
        if cursor.rowcount:
            await self.conn.execute(
                "UPDATE videos SET views = views + 1 WHERE id = ?",
                (video_id,)
            )
            await self.conn.commit()
            return True
        await self.conn.commit()
        return False

    async def increment_views(self, video_id):
        # Backward-compatible helper; new code should use count_view_once().
        await self.conn.execute("UPDATE videos SET views = views + 1 WHERE id = ?", (video_id,))
        await self.conn.commit()

    async def delete_video(self, code):
        video = await self.get_video_by_code(code)
        if video:
            await self.conn.execute("DELETE FROM video_qualities WHERE video_id = ?", (video[0],))
            await self.conn.execute("DELETE FROM videos WHERE id = ?", (video[0],))
            await self.conn.commit()
            return True
        return False

    async def has_purchased(self, user_id, video_id):
        async with self.conn.execute("SELECT 1 FROM purchases WHERE user_id = ? AND video_id = ?", (user_id, video_id)) as cursor:
            return await cursor.fetchone() is not None

    async def add_purchase(self, user_id, video_id):
        await self.conn.execute("INSERT OR IGNORE INTO purchases (user_id, video_id) VALUES (?, ?)", (user_id, video_id))
        await self.conn.commit()

    async def get_purchased_videos(self, user_id):
        async with self.conn.execute("SELECT v.id, v.code FROM purchases p JOIN videos v ON p.video_id = v.id WHERE p.user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchall()

    async def get_purchased_videos_count(self):
        async with self.conn.execute("SELECT COUNT(*) FROM purchases") as cursor:
            return (await cursor.fetchone())[0]
            
    async def get_user_purchased_count(self, user_id):
        async with self.conn.execute("SELECT COUNT(*) FROM purchases WHERE user_id = ?", (user_id,)) as cursor:
            return (await cursor.fetchone())[0]

    async def set_like(self, user_id, video_id, is_like):
        await self.conn.execute("INSERT OR REPLACE INTO likes (user_id, video_id, is_like) VALUES (?, ?, ?)", (user_id, video_id, is_like))
        await self.conn.commit()

    async def get_likes(self, video_id):
        async with self.conn.execute("SELECT SUM(CASE WHEN is_like=1 THEN 1 ELSE 0 END), SUM(CASE WHEN is_like=0 THEN 1 ELSE 0 END) FROM likes WHERE video_id = ?", (video_id,)) as cursor:
            res = await cursor.fetchone()
            return (res[0] or 0, res[1] or 0)

    async def has_liked(self, user_id, video_id):
        async with self.conn.execute("SELECT is_like FROM likes WHERE user_id = ? AND video_id = ?", (user_id, video_id)) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else None

    async def get_setting(self, key):
        async with self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else None

    async def set_setting(self, key, value):
        await self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await self.conn.commit()

    async def add_channel(self, channel_id, url, is_mandatory):
        await self.conn.execute("INSERT INTO channels (channel_id, url, is_mandatory) VALUES (?, ?, ?)", (channel_id, url, is_mandatory))
        await self.conn.commit()

    async def get_mandatory_channels(self):
        async with self.conn.execute("SELECT channel_id, url FROM channels WHERE is_mandatory = 1") as cursor:
            return await cursor.fetchall()
            
    async def get_all_channels(self):
        async with self.conn.execute("SELECT channel_id, channel_id, url, is_mandatory FROM channels") as cursor:
            return await cursor.fetchall()

    async def delete_channel(self, db_id):
        await self.conn.execute("DELETE FROM channels WHERE channel_id = ?", (db_id,))
        await self.conn.commit()
