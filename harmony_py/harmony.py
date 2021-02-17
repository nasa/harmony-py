class Collection():
    def __init__(self, id: str):
        pass


class Request():
    def __init__(self, collection: Collection, spatial: dict):
        pass


class Client():
    def submit(self, request: Request) -> int:
        return 0
