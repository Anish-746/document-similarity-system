import asyncio
import time
import sys
from pathlib import Path
from httpx import AsyncClient, ASGITransport

# Add backend directory to path so we can import 'main' and 'app'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ["DATABASE_URL"] = "postgresql+asyncpg://docsim:docsim_secret@localhost:5432/docsim"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

from main import app
from app.db.connection import init_db_pool, close_db_pool
from app.core.redis_client import close_redis

async def main():
    await init_db_pool()
    # Find a sample file
    rfc_dir = Path("../../rfc_test_data").resolve()
    if not rfc_dir.exists():
        rfc_dir = Path("../rfc_test_data").resolve()
    if not rfc_dir.exists():
        rfc_dir = Path("rfc_test_data").resolve()
        
    if not rfc_dir.exists() or not list(rfc_dir.glob("**/*.*")):
        print("Could not find rfc_test_data files.")
        return
        
    sample_file = list(rfc_dir.glob("**/*.*"))[0]
    file_bytes = sample_file.read_bytes()
    
    print(f"Testing API Latency using sample file: {sample_file.name} ({len(file_bytes)} bytes)")
    
    num_requests = 50
    latencies = []
    
    # We use ASGITransport to test the FastAPI app directly without spinning up a real web server.
    # This measures the true application latency (routing, validation, DB insert, hashing) 
    # without network overhead.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Warmup
        try:
            await ac.post(
                "/documents/upload",
                files=[("files", (sample_file.name, file_bytes, "text/plain"))]
            )
        except Exception:
            pass # ignore warmup duplicate errors
            
        print(f"Running {num_requests} sequential upload requests...")
        for i in range(num_requests):
            # We change the filename slightly so it has a different content hash if we modify the content.
            # Wait, the content hash is based on the content, not the filename!
            # If we upload the same file 50 times, it will hit DuplicateDocumentError immediately.
            # To test the FULL ingestion path, we need to alter the content slightly each time.
            unique_content = file_bytes + f"\n\nBenchmark iteration {i}".encode("utf-8")
            
            t0 = time.perf_counter()
            response = await ac.post(
                "/documents/upload",
                files=[("files", (f"benchmark_{i}.txt", unique_content, "text/plain"))]
            )
            t1 = time.perf_counter()
            
            if response.status_code == 201:
                latencies.append((t1 - t0) * 1000) # ms
            else:
                print(f"Request {i} failed: {response.status_code} - {response.text}")

    if not latencies:
        print("No successful requests to measure.")
        return
        
    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)
    
    print("\n=======================================================")
    print("              API LATENCY BENCHMARK RESULTS            ")
    print("=======================================================")
    print(f"Total Requests: {len(latencies)}")
    print(f"Average Latency: {avg_latency:.2f} ms")
    print(f"Min Latency:     {min_latency:.2f} ms")
    print(f"Max Latency:     {max_latency:.2f} ms")
    print("\nHere is your resume bullet:")
    print(f"-> Developed a non-blocking asynchronous FastAPI backend capable of processing, shingling, and hashing document uploads in an average of {avg_latency:.1f}ms per request.")
    
    await close_db_pool()
    await close_redis()

if __name__ == "__main__":
    asyncio.run(main())
