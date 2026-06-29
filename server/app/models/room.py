from app.util import CamelModel


class CreateRoomRequest(CamelModel):
    display_name: str


class CreateRoomResponse(CamelModel):
    code: str
    token: str
    player_index: int
