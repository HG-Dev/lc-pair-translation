from typing import Annotated
import annotated_types

UnsignedInt = Annotated[int, annotated_types.Ge(0)]