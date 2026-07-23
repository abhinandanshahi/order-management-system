import asyncio
import json
import os
from urllib.parse import urlsplit, urlunsplit

import websockets


def masked_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            "credentials-hidden",
            parts.fragment,
        )
    )


async def main() -> None:
    url = os.environ.get("MARKET_DATA_URL")

    if not url:
        raise RuntimeError("MARKET_DATA_URL is not configured")

    subscription = {
        "action": "subscribe",
        "symbols": ["RELIANCE", "NIFTY"],
    }

    print("Connecting to:", masked_url(url))

    try:
        async with websockets.connect(
            url,
            open_timeout=15,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
        ) as websocket:
            print("1. WebSocket handshake successful")

            await websocket.send(json.dumps(subscription))
            print("2. Subscription sent:", subscription)

            while True:
                message = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=30,
                )
                print("3. Tick received:", message)

    except asyncio.TimeoutError:
        print("Connected, but no market-data tick was received in 30 seconds")
    except websockets.ConnectionClosed as exc:
        print("WebSocket disconnected")
        print("Close code:", exc.code)
        print("Close reason:", exc.reason or "No reason supplied")
    except Exception as exc:
        print("WebSocket test failed")
        print("Error type:", type(exc).__name__)
        print("Error:", exc)


if __name__ == "__main__":
    asyncio.run(main())
