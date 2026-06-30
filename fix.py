import sys
from unittest.mock import MagicMock

m1, m2 = MagicMock(), MagicMock()
try:
    min(m1, m2)
except TypeError:
    print("TypeError caught!")
