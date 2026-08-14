
import aiosqlite
import datetime
import json

class Database:
    def __init__(self, db_path="bot.db"):
        self.db_path = db_path
        self.conn = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys=ON")
        await self.create_tables()

    async def create_tables(self):
        await self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            username TEXT,
            vip_until TEXT
        );
        CREATE TABLE IF NOT EXISTS balances(
            user_id INTEGER PRIMARY KEY,
            amount INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS referrals(
            invited_user_id INTEGER PRIMARY KEY,
            referrer_id INTEGER NOT NULL,
            reward INTEGER NOT NULL DEFAULT 500,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS referral_rules(
            user_id INTEGER PRIMARY KEY,
            accepted INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS blocked_users(
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            blocked_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS videos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            cover_id TEXT,
            post_desc TEXT,
            main_desc TEXT,
            price INTEGER DEFAULT 0,
            is_free INTEGER DEFAULT 0,
            views INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS video_qualities(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            quality TEXT NOT NULL,
            file_id TEXT NOT NULL,
            UNIQUE(video_id,quality)
        );
        CREATE TABLE IF NOT EXISTS purchases(
            user_id INTEGER NOT NULL,
            video_id INTEGER NOT NULL,
            purchased_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id,video_id)
        );
        CREATE TABLE IF NOT EXISTS likes(
            user_id INTEGER NOT NULL,
            video_id INTEGER NOT NULL,
            is_like INTEGER NOT NULL,
            PRIMARY KEY(user_id,video_id)
        );
        CREATE TABLE IF NOT EXISTS video_views(
            user_id INTEGER NOT NULL,
            video_id INTEGER NOT NULL,
            viewed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id,video_id)
        );
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS tariffs(
            days INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS channels(
            channel_id INTEGER PRIMARY KEY,
            title TEXT,
            url TEXT,
            is_mandatory INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS admins(
            user_id INTEGER PRIMARY KEY,
            role TEXT NOT NULL DEFAULT 'admin',
            added_by INTEGER,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS gifts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            days INTEGER NOT NULL,
            tariff_name TEXT NOT NULL,
            max_winners INTEGER NOT NULL,
            claimed_count INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS gift_claims(
            gift_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            claimed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(gift_id,user_id)
        );
        """)
        defaults = {
            "card":"8600 0000 0000 0000",
            "admin_link":"@admin",
            "bot_info":"Ushbu bot orqali videolarni turli sifatlarda tomosha qilishingiz mumkin.",
            "referral_reward":"500",
            "base_channel":""
        }
        for k,v in defaults.items():
            await self.conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,v))
        for days,name,price in [(1,"1 Kunlik",5000),(7,"1 Haftalik",15000),(30,"1 Oylik",25000)]:
            await self.conn.execute(
                "INSERT OR IGNORE INTO tariffs(days,name,price) VALUES(?,?,?)",
                (days,name,price)
            )
        await self.conn.commit()

    async def add_user(self,user_id,name,username):
        await self.conn.execute("""
        INSERT INTO users(user_id,name,username) VALUES(?,?,?)
        ON CONFLICT(user_id) DO UPDATE SET name=excluded.name,username=excluded.username
        """,(user_id,name or "",username or ""))
        await self.conn.execute("INSERT OR IGNORE INTO balances(user_id,amount) VALUES(?,0)",(user_id,))
        await self.conn.commit()

    async def get_user(self,user_id):
        async with self.conn.execute("SELECT * FROM users WHERE user_id=?",(user_id,)) as c:
            return await c.fetchone()

    async def total_users(self):
        async with self.conn.execute("SELECT COUNT(*) c FROM users") as c:
            return (await c.fetchone())["c"]

    async def vip_count(self):
        now=datetime.datetime.now().isoformat()
        async with self.conn.execute("SELECT COUNT(*) c FROM users WHERE vip_until IS NOT NULL AND vip_until>?",(now,)) as c:
            return (await c.fetchone())["c"]

    async def is_vip(self,user_id):
        u=await self.get_user(user_id)
        if not u or not u["vip_until"]:
            return False
        try:
            return datetime.datetime.fromisoformat(str(u["vip_until"])) > datetime.datetime.now()
        except Exception:
            return False

    async def set_vip(self,user_id,days):
        u=await self.get_user(user_id)
        now=datetime.datetime.now()
        base=now
        if u and u["vip_until"]:
            try:
                old=datetime.datetime.fromisoformat(str(u["vip_until"]))
                if old>now: base=old
            except Exception: pass
        until=base+datetime.timedelta(days=int(days))
        await self.conn.execute("UPDATE users SET vip_until=? WHERE user_id=?",(until.isoformat(),user_id))
        await self.conn.commit()
        return until

    async def revoke_vip(self,user_id):
        await self.conn.execute("UPDATE users SET vip_until=NULL WHERE user_id=?",(user_id,))
        await self.conn.commit()

    async def get_balance(self,user_id):
        await self.conn.execute("INSERT OR IGNORE INTO balances(user_id,amount) VALUES(?,0)",(user_id,))
        await self.conn.commit()
        async with self.conn.execute("SELECT amount FROM balances WHERE user_id=?",(user_id,)) as c:
            return (await c.fetchone())["amount"]

    async def add_balance(self,user_id,amount):
        await self.conn.execute("INSERT OR IGNORE INTO balances(user_id,amount) VALUES(?,0)",(user_id,))
        await self.conn.execute("UPDATE balances SET amount=amount+? WHERE user_id=?",(int(amount),user_id))
        await self.conn.commit()

    async def spend_balance(self,user_id,amount):
        cur=await self.conn.execute(
            "UPDATE balances SET amount=amount-? WHERE user_id=? AND amount>=?",
            (int(amount),user_id,int(amount))
        )
        await self.conn.commit()
        return cur.rowcount==1

    async def referral_count(self,user_id):
        async with self.conn.execute("SELECT COUNT(*) c FROM referrals WHERE referrer_id=?",(user_id,)) as c:
            return (await c.fetchone())["c"]

    async def referral_exists(self,user_id):
        async with self.conn.execute("SELECT 1 FROM referrals WHERE invited_user_id=?",(user_id,)) as c:
            return await c.fetchone() is not None

    async def add_referral(self,invited,referrer,reward):
        if invited==referrer or await self.referral_exists(invited): return False
        await self.conn.execute("INSERT INTO referrals(invited_user_id,referrer_id,reward) VALUES(?,?,?)",(invited,referrer,reward))
        await self.conn.execute("INSERT OR IGNORE INTO balances(user_id,amount) VALUES(?,0)",(referrer,))
        await self.conn.execute("UPDATE balances SET amount=amount+? WHERE user_id=?",(reward,referrer))
        await self.conn.commit()
        return True

    async def is_blocked(self,user_id):
        async with self.conn.execute("SELECT 1 FROM blocked_users WHERE user_id=?",(user_id,)) as c:
            return await c.fetchone() is not None

    async def block(self,user_id,reason=""):
        await self.conn.execute("INSERT OR REPLACE INTO blocked_users(user_id,reason) VALUES(?,?)",(user_id,reason))
        await self.conn.commit()

    async def unblock(self,user_id):
        await self.conn.execute("DELETE FROM blocked_users WHERE user_id=?",(user_id,))
        await self.conn.commit()

    async def get_setting(self,key):
        async with self.conn.execute("SELECT value FROM settings WHERE key=?",(key,)) as c:
            r=await c.fetchone()
            return r["value"] if r else None

    async def set_setting(self,key,value):
        await self.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(key,value))
        await self.conn.commit()

    async def tariffs(self):
        async with self.conn.execute("SELECT days,name,price FROM tariffs ORDER BY days") as c:
            return await c.fetchall()

    async def tariff(self,days):
        async with self.conn.execute("SELECT days,name,price FROM tariffs WHERE days=?",(days,)) as c:
            return await c.fetchone()

    async def set_tariff_price(self,days,price):
        await self.conn.execute("UPDATE tariffs SET price=? WHERE days=?",(int(price),int(days)))
        await self.conn.commit()

    async def add_channel(self,channel_id,title,url):
        await self.conn.execute(
            "INSERT OR REPLACE INTO channels(channel_id,title,url,is_mandatory) VALUES(?,?,?,1)",
            (channel_id,title,url)
        )
        await self.conn.commit()

    async def channels(self):
        async with self.conn.execute("SELECT channel_id,title,url FROM channels WHERE is_mandatory=1") as c:
            return await c.fetchall()

    async def delete_channel(self,channel_id):
        await self.conn.execute("DELETE FROM channels WHERE channel_id=?",(int(channel_id),))
        await self.conn.commit()

    async def add_admin(self,user_id,added_by,role="admin"):
        await self.conn.execute(
            "INSERT OR REPLACE INTO admins(user_id,role,added_by) VALUES(?,?,?)",
            (user_id,role,added_by)
        )
        await self.conn.commit()

    async def admin(self,user_id):
        async with self.conn.execute("SELECT * FROM admins WHERE user_id=?",(user_id,)) as c:
            return await c.fetchone()

    async def remove_admin(self,user_id):
        await self.conn.execute("DELETE FROM admins WHERE user_id=?",(user_id,))
        await self.conn.commit()

    async def all_admins(self):
        async with self.conn.execute("SELECT user_id,role,added_by FROM admins ORDER BY added_at") as c:
            return await c.fetchall()

    async def add_video(self,code,cover,post_desc,main_desc,price,is_free):
        async with self.conn.execute(
            "INSERT INTO videos(code,cover_id,post_desc,main_desc,price,is_free) VALUES(?,?,?,?,?,?)",
            (code,cover,post_desc,main_desc,int(price),int(is_free))
        ) as c:
            vid=c.lastrowid
        await self.conn.commit()
        return vid

    async def video_by_code(self,code):
        async with self.conn.execute("SELECT * FROM videos WHERE code=?",(code.strip(),)) as c:
            return await c.fetchone()

    async def video(self,vid):
        async with self.conn.execute("SELECT * FROM videos WHERE id=?",(int(vid),)) as c:
            return await c.fetchone()

    async def add_quality(self,vid,q,file_id):
        await self.conn.execute("INSERT OR REPLACE INTO video_qualities(video_id,quality,file_id) VALUES(?,?,?)",(vid,q,file_id))
        await self.conn.commit()

    async def qualities(self,vid):
        async with self.conn.execute("SELECT quality,file_id FROM video_qualities WHERE video_id=? ORDER BY id",(vid,)) as c:
            return await c.fetchall()

    async def purchased(self,user_id,vid):
        async with self.conn.execute("SELECT 1 FROM purchases WHERE user_id=? AND video_id=?",(user_id,vid)) as c:
            return await c.fetchone() is not None

    async def purchase(self,user_id,vid):
        await self.conn.execute("INSERT OR IGNORE INTO purchases(user_id,video_id) VALUES(?,?)",(user_id,vid))
        await self.conn.commit()

    async def my_videos(self,user_id):
        async with self.conn.execute(
            "SELECT v.id,v.code FROM purchases p JOIN videos v ON v.id=p.video_id WHERE p.user_id=? ORDER BY p.purchased_at",
            (user_id,)
        ) as c:
            return await c.fetchall()

    async def purchased_count(self,user_id):
        async with self.conn.execute("SELECT COUNT(*) c FROM purchases WHERE user_id=?",(user_id,)) as c:
            return (await c.fetchone())["c"]

    async def view_once(self,user_id,vid):
        cur=await self.conn.execute("INSERT OR IGNORE INTO video_views(user_id,video_id) VALUES(?,?)",(user_id,vid))
        if cur.rowcount:
            await self.conn.execute("UPDATE videos SET views=views+1 WHERE id=?",(vid,))
            await self.conn.commit()
            return True
        await self.conn.commit()
        return False

    async def like_state(self,user_id,vid):
        async with self.conn.execute("SELECT is_like FROM likes WHERE user_id=? AND video_id=?",(user_id,vid)) as c:
            r=await c.fetchone()
            return r["is_like"] if r else None

    async def set_like(self,user_id,vid,value):
        await self.conn.execute("INSERT OR REPLACE INTO likes(user_id,video_id,is_like) VALUES(?,?,?)",(user_id,vid,value))
        await self.conn.commit()

    async def like_counts(self,vid):
        async with self.conn.execute(
            "SELECT SUM(CASE WHEN is_like=1 THEN 1 ELSE 0 END) likes,SUM(CASE WHEN is_like=0 THEN 1 ELSE 0 END) dislikes FROM likes WHERE video_id=?",
            (vid,)
        ) as c:
            r=await c.fetchone()
            return (r["likes"] or 0,r["dislikes"] or 0)

    async def delete_video(self,code):
        v=await self.video_by_code(code)
        if not v: return False
        vid=v["id"]
        for table in ("purchases","likes","video_views","video_qualities"):
            await self.conn.execute(f"DELETE FROM {table} WHERE video_id=?",(vid,))
        await self.conn.execute("DELETE FROM videos WHERE id=?",(vid,))
        await self.conn.commit()
        return True

    async def create_gift(self,days,name,count):
        async with self.conn.execute(
            "INSERT INTO gifts(days,tariff_name,max_winners) VALUES(?,?,?)",
            (days,name,count)
        ) as c: gid=c.lastrowid
        await self.conn.commit()
        return gid

    async def claim_gift(self,gid,user_id):
        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            async with self.conn.execute("SELECT * FROM gifts WHERE id=?",(gid,)) as c: g=await c.fetchone()
            if not g:
                await self.conn.rollback(); return "missing",None
            async with self.conn.execute("SELECT 1 FROM gift_claims WHERE gift_id=? AND user_id=?",(gid,user_id)) as c:
                if await c.fetchone():
                    await self.conn.rollback(); return "already",g
            if not g["active"] or g["claimed_count"]>=g["max_winners"]:
                await self.conn.rollback(); return "full",g
            if await self.is_vip(user_id):
                await self.conn.rollback(); return "vip",g
            await self.conn.execute("INSERT INTO gift_claims(gift_id,user_id) VALUES(?,?)",(gid,user_id))
            n=g["claimed_count"]+1
            await self.conn.execute("UPDATE gifts SET claimed_count=?,active=? WHERE id=?",(n,0 if n>=g["max_winners"] else 1,gid))
            await self.conn.commit()
            return "won",(g,n)
        except Exception:
            await self.conn.rollback()
            raise

    async def gift_winners(self,gid):
        async with self.conn.execute(
            "SELECT u.user_id,u.name,u.username FROM gift_claims gc JOIN users u ON u.user_id=gc.user_id WHERE gc.gift_id=? ORDER BY gc.claimed_at",
            (gid,)
        ) as c: return await c.fetchall()

    async def stats(self):
        async with self.conn.execute("SELECT COUNT(*) c FROM videos") as c: vids=(await c.fetchone())["c"]
        async with self.conn.execute("SELECT COUNT(*) c FROM purchases") as c: purchases=(await c.fetchone())["c"]
        async with self.conn.execute("SELECT COALESCE(SUM(views),0) c FROM videos") as c: views=(await c.fetchone())["c"]
        return vids,purchases,views
