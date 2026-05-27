"""Redpanda (Kafka API) helpers shared by ingestion (produce) and worker (consume)."""

from __future__ import annotations

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer


class Producer:
    def __init__(self, brokers: str) -> None:
        self._p = AIOKafkaProducer(bootstrap_servers=brokers, acks="all", enable_idempotence=True)

    async def start(self) -> None:
        await self._p.start()

    async def stop(self) -> None:
        await self._p.stop()

    async def send(self, topic: str, *, key: str, value: bytes) -> None:
        # keying by request_id pins a request to one partition: ordering + dedupe locality
        await self._p.send_and_wait(topic, value=value, key=key.encode())


def make_consumer(*, topic: str, brokers: str, group: str) -> AIOKafkaConsumer:
    return AIOKafkaConsumer(
        topic,
        bootstrap_servers=brokers,
        group_id=group,
        enable_auto_commit=False,  # commit only after a successful write (at-least-once)
        auto_offset_reset="earliest",
    )
