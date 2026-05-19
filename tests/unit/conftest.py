import sys
from unittest.mock import MagicMock

sys.modules["pydantic"] = MagicMock()
sys.modules["pydantic.BaseModel"] = MagicMock()
sys.modules["pydantic.Field"] = MagicMock()
sys.modules["yaml"] = MagicMock()
