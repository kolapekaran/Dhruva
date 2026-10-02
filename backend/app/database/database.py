class InMemoryStateRepository:
    def __init__(self):
        self._history = []
    def append(self, state):
        self._history.append(state)
    def all(self):
        return list(self._history)
    def latest(self):
        return self._history[-1] if self._history else None
