"""End-to-end WebSocket test for the CRM agent."""
import asyncio
import json
import websockets
import urllib.request

BACKEND_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/chat"


def check_health() -> bool:
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/health", timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False


async def test_ws() -> dict:
    results = {
        "websocket_connect": False,
        "message_sent": False,
        "response_received": False,
        "end_marker": False,
        "no_runtime_errors": True,
    }
    try:
        async with websockets.connect(WS_URL, open_timeout=5, close_timeout=5) as ws:
            results["websocket_connect"] = True
            print("[OK] WebSocket connected")

            # Send a simple list-doctors query (rule-based, no LLM needed)
            msg = "List all doctors"
            await ws.send(msg)
            results["message_sent"] = True
            print(f"[OK] Sent: {msg}")

            # Collect responses
            chunks = []
            try:
                while True:
                    chunk = await asyncio.wait_for(ws.recv(), timeout=10)
                    chunks.append(chunk)
                    if chunk == "__END__":
                        results["end_marker"] = True
                        break
            except asyncio.TimeoutError:
                print("[WARN] Timeout waiting for __END__")

            if len(chunks) > 1:
                results["response_received"] = True
                print(f"[OK] Received {len(chunks)} chunks")
                # Check last chunk before __END__ is valid JSON
                for c in chunks[:-1]:
                    try:
                        data = json.loads(c)
                        print(f"[OK] Response payload: {data.get('action')} / {data.get('status')}")
                    except json.JSONDecodeError:
                        print(f"[INFO] Non-JSON chunk: {c[:100]}")
            else:
                print("[FAIL] No response chunks received")
                results["no_runtime_errors"] = False

    except Exception as e:
        print(f"[FAIL] WebSocket error: {e}")
        results["no_runtime_errors"] = False

    return results


def main():
    print("=" * 50)
    print("CRM Agent WebSocket E2E Test")
    print("=" * 50)

    if not check_health():
        print("\n[FAIL] Backend health check failed. Is the server running?")
        print("Start it with: cd backend && uvicorn app.main:app --reload")
        return
    print("[OK] Backend health check passed")

    results = asyncio.run(test_ws())

    print("\n" + "=" * 50)
    print("Results:")
    all_pass = all(results.values())
    for k, v in results.items():
        status = "PASS" if v else "FAIL"
        print(f"  {k}: {status}")
    print("=" * 50)
    print(f"Overall: {'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    exit(main())

