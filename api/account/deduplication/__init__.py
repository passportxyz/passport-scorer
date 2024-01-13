from enum import Enum


class Rules(Enum):
    LIFO = "LIFO"
    FIFO = "FIFO"  # DEPRECATED - this shall not be used any more

    @classmethod
    def choices(cls):
        return [(i.value, i.value) for i in cls]
