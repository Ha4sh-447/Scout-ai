import operator
from typing import Annotated
from models.config import EmailConfig
from typing import TypedDict

from models.resume import MatchedJob


class NotificationState(TypedDict):
    user_id: str
    jobs_with_drafts: list[MatchedJob]
    email_cfg: EmailConfig
    run_label: str

    email_sent: str
    email_preview: str

    errors: Annotated[list[str], operator.add]
    status: str
