class Issue:
    def __init__(self):
        self.issue_id: str = None
        self.title: str = None
        self.status: str = None
        self.created_date: str = None
        self.start_date: str = None
        self.done_date: str = None

    def to_dict(self):
        return {
            "issue_id": self.issue_id,
            "title": self.title,
            "status": self.status,
            "created_date": self.created_date,
            "start_date": self.start_date,
            "done_date": self.done_date
        }