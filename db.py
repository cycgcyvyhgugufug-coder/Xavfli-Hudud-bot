import aiosqlite
import datetime


class Database:
    def __init__(self, db_path="bot.db"):
        self.db_path = db_path

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.create_tables()

    async def create_tables(self):
        await self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                username TEXT,
                balance INTEGER NOT NULL DEFAULT 0,
                vip_until TIMESTAMP,
                referred_by INTEGER,
                rules_accepted INTEGER NOT NULL DEFAULT 0,
                blocked INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                video_type TEXT NOT NULL DEFAULT 'paid',
                cover_id TEXT,
                post_desc TEXT,
                main_desc TEXT,
                price INTEGER DEFAULT 0,
                free_file_id TEXT,
                views INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                url TEXT
            );

            CREATE TABLE IF NOT EXISTS ad_channels (
                video_type TEXT PRIMARY KEY,
                channel_id INTEGER,
                url TEXT
            );

            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                can_edit INTEGER NOT NULL DEFAULT 0,
                can_confirm_payments INTEGER NOT NULL DEFAULT 0,
                can_manage_admins INTEGER NOT NULL DEFAULT 0,
                can_view_users INTEGER NOT NULL DEFAULT 0,
                added_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS balance_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                receipt_photo_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                reject_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

        defaults = {
            'card': "8600 0000 0000 0000",
            'admin_link': "@admin",
            'vip_price_1': "5000",
            'vip_price_7': "15000",
            'vip_price_30': "25000",
            'bot_info': (
                "Xavfli Hudud botiga xush kelibsiz!\n\n"
                "Bu bot orqali siz videolarni donalab sotib olishingiz yoki "
                "VIP tarifni xarid qilib barcha videolarni cheklovsiz "
                "ko'rishingiz mumkin."
            ),
        }
        for key, value in defaults.items():
            await self.conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value)
            )
        await self.conn.commit()

    # ==================== USERS ====================

    async def add_user(self, user_id, name, username, referred_by=None):
        """Foydalanuvchi mavjud bo'lmasa qo'shadi. Qaytaradi: (is_new, user_row)."""
        existing = await self.get_user(user_id)
        if existing:
            await self.conn.execute(
                "UPDATE users SET name=?, username=? WHERE user_id=?",
                (name, username, user_id)
            )
            await self.conn.commit()
            return False, existing
        await self.conn.execute(
            "INSERT INTO users (user_id, name, username, referred_by) VALUES (?, ?, ?, ?)",
            (user_id, name, username, referred_by)
        )
        await self.conn.commit()
        new_user = await self.get_user(user_id)
        return True, new_user

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

    async def get_new_users_since(self, since_dt):
        async with self.conn.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (since_dt,)) as cursor:
            return (await cursor.fetchone())[0]

    async def set_vip(self, user_id, days):
        now = datetime.datetime.now()
        user = await self.get_user(user_id)
        current_until = None
        if user and user[4]:
            try:
                current_until = datetime.datetime.fromisoformat(str(user[4]))
            except (TypeError, ValueError):
                current_until = None
        base = current_until if current_until and current_until > now else now
        vip_until = base + datetime.timedelta(days=days)
        await self.conn.execute("UPDATE users SET vip_until = ? WHERE user_id = ?", (vip_until, user_id))
        await self.conn.commit()
        return vip_until

    async def is_vip(self, user_id):
        user = await self.get_user(user_id)
        if user and user[4]:
            try:
                vip_until = datetime.datetime.fromisoformat(str(user[4]))
            except (TypeError, ValueError):
                return False
            return vip_until > datetime.datetime.now()
        return False

    async def revoke_vip(self, user_id):
        user = await self.get_user(user_id)
        if not user:
            return "not_found"
        if not await self.is_vip(user_id):
            return "no_vip"
        await self.conn.execute("UPDATE users SET vip_until=NULL WHERE user_id=?", (user_id,))
        await self.conn.commit()
        return "revoked"

    async def get_broadcast_users(self, target):
        now = datetime.datetime.now()
        if target == "vip":
            query = "SELECT user_id FROM users WHERE vip_until IS NOT NULL AND vip_until > ? AND blocked = 0"
            params = (now,)
        elif target == "regular":
            query = "SELECT user_id FROM users WHERE (vip_until IS NULL OR vip_until <= ?) AND blocked = 0"
            params = (now,)
        else:
            query = "SELECT user_id FROM users WHERE blocked = 0"
            params = ()
        async with self.conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def get_non_vip_users(self):
        now = datetime.datetime.now()
        async with self.conn.execute(
            "SELECT user_id FROM users WHERE (vip_until IS NULL OR vip_until <= ?) AND blocked = 0",
            (now,)
        ) as cursor:
            rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def set_blocked(self, user_id, blocked: bool):
        await self.conn.execute("UPDATE users SET blocked=? WHERE user_id=?", (1 if blocked else 0, user_id))
        await self.conn.commit()

    async def is_blocked(self, user_id):
        user = await self.get_user(user_id)
        return bool(user and user[7])

    # ---------- BALANS ----------

    async def get_balance(self, user_id):
        user = await self.get_user(user_id)
        return user[3] if user else 0

    async def change_balance(self, user_id, delta, tx_type, description=None):
        """Balansni atomik ravishda o'zgartiradi. Manfiy delta yetarli bo'lmasa False qaytaradi."""
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            async with self.conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)) as cur:
                row = await cur.fetchone()
            if not row:
                await self.conn.rollback()
                return False, 0
            current = row[0]
            new_balance = current + delta
            if new_balance < 0:
                await self.conn.rollback()
                return False, current
            await self.conn.execute("UPDATE users SET balance=? WHERE user_id=?", (new_balance, user_id))
            await self.conn.execute(
                "INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)",
                (user_id, tx_type, delta, description)
            )
            await self.conn.commit()
            return True, new_balance
        except Exception:
            await self.conn.rollback()
            raise

    async def get_total_topped_up(self):
        async with self.conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='topup'"
        ) as cur:
            return (await cur.fetchone())[0]

    # ---------- REFERAL ----------

    async def get_referral_count(self, user_id):
        async with self.conn.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,)) as cur:
            return (await cur.fetchone())[0]

    async def get_total_referrals(self):
        async with self.conn.execute("SELECT COUNT(*) FROM users WHERE referred_by IS NOT NULL") as cur:
            return (await cur.fetchone())[0]

    async def set_rules_accepted(self, user_id):
        await self.conn.execute("UPDATE users SET rules_accepted=1 WHERE user_id=?", (user_id,))
        await self.conn.commit()

    async def has_accepted_rules(self, user_id):
        user = await self.get_user(user_id)
        return bool(user and user[6])

    # ---------- BALANS TO'LDIRISH SO'ROVLARI ----------

    async def create_balance_request(self, user_id, amount, receipt_photo_id):
        async with self.conn.execute(
            "INSERT INTO balance_requests (user_id, amount, receipt_photo_id) VALUES (?, ?, ?)",
            (user_id, amount, receipt_photo_id)
        ) as cur:
            req_id = cur.lastrowid
        await self.conn.commit()
        return req_id

    async def get_balance_request(self, req_id):
        async with self.conn.execute("SELECT * FROM balance_requests WHERE id=?", (req_id,)) as cur:
            return await cur.fetchone()

    async def set_balance_request_status(self, req_id, status, reject_reason=None):
        await self.conn.execute(
            "UPDATE balance_requests SET status=?, reject_reason=? WHERE id=?",
            (status, reject_reason, req_id)
        )
        await self.conn.commit()

    # ==================== VIDEOS ====================

    async def add_paid_video(self, code, cover_id, post_desc, main_desc, price):
        async with self.conn.execute(
            "INSERT INTO videos (code, video_type, cover_id, post_desc, main_desc, price) VALUES (?, 'paid', ?, ?, ?, ?)",
            (code, cover_id, post_desc, main_desc, price)
        ) as cursor:
            video_id = cursor.lastrowid
        await self.conn.commit()
        return video_id

    async def add_free_video(self, code, file_id):
        async with self.conn.execute(
            "INSERT INTO videos (code, video_type, free_file_id, price) VALUES (?, 'free', ?, 0)",
            (code, file_id)
        ) as cursor:
            video_id = cursor.lastrowid
        await self.conn.commit()
        return video_id

    async def add_video_quality(self, video_id, quality, file_id):
        await self.conn.execute(
            "INSERT INTO video_qualities (video_id, quality, file_id) VALUES (?, ?, ?)",
            (video_id, quality, file_id)
        )
        await self.conn.commit()

    async def get_video_by_code(self, code):
        async with self.conn.execute("SELECT * FROM videos WHERE code = ?", (code,)) as cursor:
            return await cursor.fetchone()

    async def get_video(self, video_id):
        async with self.conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)) as cursor:
            return await cursor.fetchone()

    async def get_video_qualities(self, video_id):
        async with self.conn.execute(
            "SELECT quality, file_id FROM video_qualities WHERE video_id = ?", (video_id,)
        ) as cursor:
            return await cursor.fetchall()

    async def count_view_once(self, user_id, video_id):
        cursor = await self.conn.execute(
            "INSERT OR IGNORE INTO video_views (user_id, video_id) VALUES (?, ?)",
            (user_id, video_id)
        )
        if cursor.rowcount:
            await self.conn.execute("UPDATE videos SET views = views + 1 WHERE id = ?", (video_id,))
            await self.conn.commit()
            return True
        await self.conn.commit()
        return False

    async def delete_video(self, code):
        """Videoni va unga bog'liq BARCHA yozuvlarni (xaridlar, layklar, ko'rishlar) o'chiradi."""
        video = await self.get_video_by_code(code)
        if not video:
            return False
        video_id = video[0]
        await self.conn.execute("DELETE FROM video_qualities WHERE video_id = ?", (video_id,))
        await self.conn.execute("DELETE FROM purchases WHERE video_id = ?", (video_id,))
        await self.conn.execute("DELETE FROM likes WHERE video_id = ?", (video_id,))
        await self.conn.execute("DELETE FROM video_views WHERE video_id = ?", (video_id,))
        await self.conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        await self.conn.commit()
        return True

    async def has_purchased(self, user_id, video_id):
        async with self.conn.execute(
            "SELECT 1 FROM purchases WHERE user_id = ? AND video_id = ?", (user_id, video_id)
        ) as cursor:
            return await cursor.fetchone() is not None

    async def add_purchase(self, user_id, video_id):
        await self.conn.execute(
            "INSERT OR IGNORE INTO purchases (user_id, video_id) VALUES (?, ?)", (user_id, video_id)
        )
        await self.conn.commit()

    async def get_purchased_videos(self, user_id):
        async with self.conn.execute(
            """SELECT v.id, v.code FROM purchases p
               JOIN videos v ON p.video_id = v.id
               WHERE p.user_id = ? ORDER BY p.purchased_at DESC""",
            (user_id,)
        ) as cursor:
            return await cursor.fetchall()

    async def get_purchased_videos_count(self):
        async with self.conn.execute("SELECT COUNT(*) FROM purchases") as cursor:
            return (await cursor.fetchone())[0]

    async def get_purchases_since(self, since_dt):
        async with self.conn.execute(
            "SELECT COUNT(*) FROM purchases WHERE purchased_at >= ?", (since_dt,)
        ) as cursor:
            return (await cursor.fetchone())[0]

    async def set_like(self, user_id, video_id, is_like):
        await self.conn.execute(
            "INSERT OR REPLACE INTO likes (user_id, video_id, is_like) VALUES (?, ?, ?)",
            (user_id, video_id, is_like)
        )
        await self.conn.commit()

    async def get_likes(self, video_id):
        async with self.conn.execute(
            "SELECT SUM(CASE WHEN is_like=1 THEN 1 ELSE 0 END), SUM(CASE WHEN is_like=0 THEN 1 ELSE 0 END) "
            "FROM likes WHERE video_id = ?", (video_id,)
        ) as cursor:
            res = await cursor.fetchone()
            return (res[0] or 0, res[1] or 0)

    async def has_liked(self, user_id, video_id):
        async with self.conn.execute(
            "SELECT is_like FROM likes WHERE user_id = ? AND video_id = ?", (user_id, video_id)
        ) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else None

    # ==================== SETTINGS ====================

    async def get_setting(self, key):
        async with self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            res = await cursor.fetchone()
            return res[0] if res else None

    async def set_setting(self, key, value):
        await self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await self.conn.commit()

    async def get_vip_prices(self):
        return {
            1: int(await self.get_setting("vip_price_1") or 5000),
            7: int(await self.get_setting("vip_price_7") or 15000),
            30: int(await self.get_setting("vip_price_30") or 25000),
        }

    # ==================== MAJBURIY KANALLAR ====================

    async def add_channel(self, channel_id, url):
        await self.conn.execute("INSERT OR REPLACE INTO channels (channel_id, url) VALUES (?, ?)", (channel_id, url))
        await self.conn.commit()

    async def get_mandatory_channels(self):
        async with self.conn.execute("SELECT channel_id, url FROM channels") as cursor:
            return await cursor.fetchall()

    async def delete_channel(self, channel_id):
        await self.conn.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        await self.conn.commit()

    # ==================== REKLAMA KANALLARI ====================

    async def set_ad_channel(self, video_type, channel_id, url):
        await self.conn.execute(
            "INSERT OR REPLACE INTO ad_channels (video_type, channel_id, url) VALUES (?, ?, ?)",
            (video_type, channel_id, url)
        )
        await self.conn.commit()

    async def get_ad_channel(self, video_type):
        async with self.conn.execute(
            "SELECT channel_id, url FROM ad_channels WHERE video_type=?", (video_type,)
        ) as cur:
            return await cur.fetchone()

    async def delete_ad_channel(self, video_type):
        await self.conn.execute("DELETE FROM ad_channels WHERE video_type=?", (video_type,))
        await self.conn.commit()

    # ==================== ADMINLAR ====================

    async def add_admin(self, user_id, added_by, permissions=None):
        permissions = permissions or {}
        await self.conn.execute(
            """INSERT INTO admins (user_id, can_edit, can_confirm_payments, can_manage_admins, can_view_users, added_by)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 can_edit=excluded.can_edit,
                 can_confirm_payments=excluded.can_confirm_payments,
                 can_manage_admins=excluded.can_manage_admins,
                 can_view_users=excluded.can_view_users""",
            (
                user_id,
                int(bool(permissions.get("can_edit", 0))),
                int(bool(permissions.get("can_confirm_payments", 0))),
                int(bool(permissions.get("can_manage_admins", 0))),
                int(bool(permissions.get("can_view_users", 0))),
                added_by,
            )
        )
        await self.conn.commit()

    async def remove_admin(self, user_id):
        await self.conn.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
        await self.conn.commit()

    async def get_admin(self, user_id):
        async with self.conn.execute("SELECT * FROM admins WHERE user_id=?", (user_id,)) as cur:
            return await cur.fetchone()

    async def get_all_admins(self):
        async with self.conn.execute("SELECT * FROM admins") as cur:
            return await cur.fetchall()

    async def get_payment_confirm_admins(self):
        """can_confirm_payments=1 bo'lgan qo'shimcha adminlarning user_id lari."""
        async with self.conn.execute(
            "SELECT user_id FROM admins WHERE can_confirm_payments=1"
        ) as cur:
            rows = await cur.fetchall()
        return [r[0] for r in rows]

    # ==================== GIFT (RANDOM) ====================

    async def create_gift_campaign(self, days, tariff_name, max_winners):
        async with self.conn.execute(
            "INSERT INTO gift_campaigns (days, tariff_name, max_winners) VALUES (?, ?, ?)",
            (days, tariff_name, max_winners)
        ) as cursor:
            gift_id = cursor.lastrowid
        await self.conn.commit()
        return gift_id

    async def claim_gift(self, gift_id, user_id):
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            async with self.conn.execute(
                "SELECT id, days, tariff_name, max_winners, claimed_count, active, completed_notified "
                "FROM gift_campaigns WHERE id = ?", (gift_id,)
            ) as cur:
                gift = await cur.fetchone()
            if not gift:
                await self.conn.rollback()
                return "not_found", None

            async with self.conn.execute(
                "SELECT 1 FROM gift_claims WHERE gift_id=? AND user_id=?", (gift_id, user_id)
            ) as cur:
                if await cur.fetchone():
                    await self.conn.rollback()
                    return "already", gift

            if gift[5] != 1:
                await self.conn.rollback()
                return "full", gift

            async with self.conn.execute("SELECT vip_until FROM users WHERE user_id=?", (user_id,)) as cur:
                user = await cur.fetchone()
            if not user:
                await self.conn.rollback()
                return "not_found", gift

            if user[0]:
                try:
                    if datetime.datetime.fromisoformat(str(user[0])) > datetime.datetime.now():
                        await self.conn.rollback()
                        return "vip", gift
                except (TypeError, ValueError):
                    pass

            new_count = gift[4] + 1
            if new_count > gift[3]:
                await self.conn.rollback()
                return "full", gift

            await self.conn.execute("INSERT INTO gift_claims (gift_id,user_id) VALUES (?,?)", (gift_id, user_id))
            completed = new_count >= gift[3]
            await self.conn.execute(
                "UPDATE gift_campaigns SET claimed_count=?, active=?, completed_notified=? WHERE id=?",
                (new_count, 0 if completed else 1, gift[6], gift_id)
            )
            await self.conn.commit()
            return "won", (gift[0], gift[1], gift[2], gift[3], new_count, 0 if completed else 1, 1 if completed else gift[6])
        except Exception:
            await self.conn.rollback()
            raise

    async def get_gift_winners(self, gift_id):
        async with self.conn.execute(
            "SELECT u.user_id, u.name, u.username FROM gift_claims g JOIN users u ON u.user_id=g.user_id "
            "WHERE g.gift_id=? ORDER BY g.claimed_at ASC", (gift_id,)
        ) as cur:
            return await cur.fetchall()

    async def mark_gift_completed_notified(self, gift_id):
        async with self.conn.execute(
            "UPDATE gift_campaigns SET completed_notified=1 WHERE id=? AND completed_notified=0", (gift_id,)
        ) as cur:
            changed = cur.rowcount
        await self.conn.commit()
        return changed == 1
