import asyncio
import json
import time

from redis import Redis

from aicoding_shared.config import get_settings
from aicoding_shared.db import init_db

from app.main import process_audit


async def main() -> None:
    init_db()
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    print(f"video-worker listening on Redis queue: {settings.video_audit_queue}", flush=True)
    while True:
        try:
            item = redis.blpop(settings.video_audit_queue, timeout=5)
            if item is None:
                await asyncio.sleep(0.2)
                continue
            _, payload_raw = item
            payload = json.loads(payload_raw)
            result = await process_audit(int(payload["audit_id"]))
            print(json.dumps(result, ensure_ascii=False), flush=True)
        except Exception as exc:
            print(f"video-worker error: {exc}", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
