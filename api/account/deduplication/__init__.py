from enum import Enum


class Rules(Enum):
    LIFO = "LIFO"
    FIFO = "FIFO"

    @classmethod
    def choices(cls):
        return [(i.value, i.value) for i in cls]
