import httpx


class HomeAssistant:
    def __init__(self, base_url: str, token: str):
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
            follow_redirects=False,
        )

    async def cameras(self) -> list[dict]:
        response = await self.client.get("states")
        response.raise_for_status()
        return sorted(
            [{"entity_id": item["entity_id"],
              "name": item.get("attributes", {}).get("friendly_name", item["entity_id"]),
              "state": item["state"]}
             for item in response.json() if item["entity_id"].startswith("camera.")],
            key=lambda item: item["name"].lower(),
        )

    async def snapshot(self, entity_id: str) -> bytes:
        # Stream with a hard size limit; never persist an HTML/error response as a frame.
        async with self.client.stream("GET", f"camera_proxy/{entity_id}") as response:
            response.raise_for_status()
            if not response.headers.get("content-type", "").lower().startswith("image/"):
                raise ValueError("The camera did not return an image.")
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > 20 * 1024 * 1024:
                    raise ValueError("The camera snapshot exceeded 20 MB.")
            return bytes(chunks)

    async def close(self):
        await self.client.aclose()
