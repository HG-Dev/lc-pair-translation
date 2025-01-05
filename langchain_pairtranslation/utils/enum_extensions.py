from functools import total_ordering

def enum_ordering(cls):
    def __lt__(self, other):
        if type(other) == type(self):
            return self.value < other.value

        raise ValueError("Cannot compare different Enums")

    setattr(cls, '__lt__', __lt__)
    return total_ordering(cls)