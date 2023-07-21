from cicada.domain.triggers import Trigger


# TODO: remove this function
def build_trigger(type: str) -> Trigger:
    class C(Trigger):
        pass

    C.type = type

    return C(provider="github", repository_url="", sha=None)
