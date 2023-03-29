from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from cicada.api.di import DiContainer

Di = Annotated[DiContainer, Depends()]

oauth2_schema = OAuth2PasswordBearer(tokenUrl="login")
JWTToken = Annotated[str, Depends(oauth2_schema)]

PasswordForm = Annotated[OAuth2PasswordRequestForm, Depends()]
