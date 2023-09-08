from getpass import getpass

import hvac  # type: ignore

from cicada.api.settings import VaultSettings


def get_vault_client(*, login: bool = True) -> hvac.Client:  # type: ignore
    settings = VaultSettings()

    client = hvac.Client(
        url=settings.address,
        cert=(settings.client_cert, settings.client_key),
        verify=settings.server_cert,
    )

    if login:
        client.auth.userpass.login(
            username="cicada",
            password=settings.user_password,
        )

    return client


# TODO: what happens if key is incorrect?
# TODO: calculate and display threshold/totals
def unlock_vault(client: hvac.Client) -> None:  # type: ignore
    i = 1

    while client.sys.is_sealed():
        key = getpass(f"Unlock key {i} (hidden): ")

        client.sys.submit_unseal_key(key)

        i += 1


if __name__ == "__main__":
    unlock_vault(get_vault_client(login=False))
