import uvicorn

from orion.config import settings


def main() -> None:
    uvicorn.run(
        "orion.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
