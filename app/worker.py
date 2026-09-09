# app/worker.py
import asyncio

async def main():
    print("Worker standing by for stream consumer implementation...")
    while True:
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())