from JiraApiClient.issue import Issue

class Epic:
    def __init__(self):
        self.key: str = None
        self.summary: str = None
        self.status: str = None
        self.issues: list[Issue] = []
        self.start_date: str = None
        self.due_date:str = None

