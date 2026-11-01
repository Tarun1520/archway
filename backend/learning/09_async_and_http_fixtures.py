"""
Lesson 09: async/await, and calling an HTTP API with a fixture
==============================================================

What you learn here
    - `async` code lets one program WAIT for many slow things at once
      (network calls, database reads) instead of one after another.
    - httpx is the HTTP client. It can be given a fake "transport" that
      answers requests from recorded data instead of the internet. That is
      the whole idea behind Archway's FIXTURE MODE.

How to run (from the project root)
    backend/.venv/bin/python backend/learning/09_async_and_http_fixtures.py

Where Archway uses this
    backend/app/research/ will call the GitHub API with httpx. In fixture mode
    (tests, CI, offline demos) the same client code runs against recorded
    responses, so nothing is charged and nothing depends on the network.
"""

import asyncio
import time

import httpx


# -----------------------------------------------------------------------------
# Part 1: why async
# -----------------------------------------------------------------------------
async def slow_task(name: str, seconds: float) -> str:
    # LEARNING NOTE: `await` means "pause THIS function here and let other
    #   work run until the thing I am waiting for is ready".
    #   asyncio.sleep stands in for a slow network call.
    await asyncio.sleep(seconds)
    return f"{name} done"


async def demo_concurrency() -> None:
    print("PART 1: three 0.3-second waits")

    started = time.perf_counter()
    for name in ["a", "b", "c"]:
        await slow_task(name, 0.3)  # one at a time
    print(f"  one after another : {time.perf_counter() - started:.1f}s")

    started = time.perf_counter()
    # gather starts all three, then waits for all of them together.
    results = await asyncio.gather(*(slow_task(name, 0.3) for name in ["a", "b", "c"]))
    print(f"  all at once       : {time.perf_counter() - started:.1f}s  {results}")


# -----------------------------------------------------------------------------
# Part 2: an HTTP client that can run from a fixture
# -----------------------------------------------------------------------------
# FIXTURE DATA: a made-up, recorded-style response. Not real GitHub data.
RECORDED_RESPONSES = {
    "/repos/example/notes-md": {"full_name": "example/notes-md", "stargazers_count": 1200, "archived": False},
}


def fixture_handler(request: httpx.Request) -> httpx.Response:
    """Answer a request from RECORDED_RESPONSES instead of the network."""
    recorded = RECORDED_RESPONSES.get(request.url.path)
    if recorded is None:
        return httpx.Response(404, json={"message": "Not Found"})
    return httpx.Response(200, json=recorded)


async def get_repo(client: httpx.AsyncClient, full_name: str) -> dict | None:
    """Fetch one repository. Returns None when it cannot be fetched.

    LEARNING NOTE: this function does not know or care whether `client` is
    talking to the real internet or to a fixture. That is "plug and play":
    the caller decides which client to pass in.
    """
    response = await client.get(f"/repos/{full_name}")
    if response.status_code != 200:
        return None  # a failed fetch stays a failure; we never invent data
    return response.json()


async def demo_fixture_client() -> None:
    print("\nPART 2: the same client code, answered by a fixture")
    transport = httpx.MockTransport(fixture_handler)
    async with httpx.AsyncClient(transport=transport, base_url="https://api.github.com") as client:
        print("  known repo  :", await get_repo(client, "example/notes-md"))
        print("  unknown repo:", await get_repo(client, "example/does-not-exist"))


async def main() -> None:
    await demo_concurrency()
    await demo_fixture_client()


if __name__ == "__main__":
    # asyncio.run starts the "event loop", the engine that runs async code.
    asyncio.run(main())
