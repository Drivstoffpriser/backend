import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger("drivstoffpriser")
