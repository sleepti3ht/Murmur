from abc import ABC, abstractmethod

class BaseAdapter(ABC):
    @abstractmethod
    def get_changes(self) -> list[dict]:
        """
        Returns a list of changed lines:
        [
            {
                "file": "path/to/file",
                "line_number": 10,
                "content": "string with potential secret"
            }
        ]
        """
        raise NotImplementedError