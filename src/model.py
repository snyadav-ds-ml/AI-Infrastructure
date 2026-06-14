class ModelWrapper:
    def __init__(self) -> None:
        self._model = None
        self._loaded = False

    def load(self) -> None:
        raise NotImplementedError("Implement in T2")

    def predict(self, image) -> dict:
        raise NotImplementedError("Implement in T2")

    def is_loaded(self) -> bool:
        return self._loaded


model = ModelWrapper()
