import os
import requests
from requests.auth import HTTPBasicAuth
from JiraApiClient.epic import Epic
from JiraApiClient.issue import Issue

class JiraProjectMetaData:
    def __init__(self):
        self.base_url: str = ""
        self.project_key: str = ""
        self.start_data_field_id: str = ""
        self.actual_start_date_field_id: str = ""
        self.actual_end_date_field_id: str = ""

    def __str__(self):
        return (f"JiraProjectMetaData(base_url={self.base_url},\n"
                f"project_key={self.project_key},\n"
                f"start_data_field_id={self.start_data_field_id},\n"
                f"actual_start_date_field_id={self.actual_start_date_field_id},\n"
                f"actual_end_date_field_id={self.actual_end_date_field_id})")

class AuthData:
    def __init__(self, username: str, api_token: str):
        self.username = username
        self.api_token = api_token

    def from_env():
        username = os.environ.get("JIRA_USERNAME")
        api_token = os.environ.get("JIRA_API_TOKEN")
        if not username or not api_token:
            raise ValueError("JIRA_USERNAME and JIRA_API_TOKEN environment variables must be set.")
        return AuthData(username, api_token)

class JiraClient:
    def __init__(self, jira_project: JiraProjectMetaData, auth_data: AuthData):
        if not jira_project:
            raise ValueError("jira_project parameter is required.")
        
        self.jira_project = jira_project
        self.base_url = jira_project.base_url
        self.project = jira_project.project_key
        
        self.auth = HTTPBasicAuth(auth_data.username, auth_data.api_token)

        self.headers = {
            "Accept": "application/json"
        }

    def get_server_info(self):
        url = f"{self.base_url}/serverInfo"
        response = requests.get(url, headers=self.headers, auth=self.auth)
        response.raise_for_status()
        return response.json()

    def list_epics(self):
        # JQL to get all epics in project that are not done
        jql = f"project={self.project} AND issuetype=Epic AND statusCategory != Done"
        url = f"{self.base_url}/search/jql"
        params = {
            "jql": jql,
            "fields": f"summary,description,status,{self.jira_project.start_data_field_id},duedate"
        }
        response = requests.get(url, headers=self.headers, params=params, auth=self.auth)
        response.raise_for_status()
        epic_issues = response.json().get("issues", [])

        return [
            {
                "key": issue["key"],
                "summary": issue["fields"]["summary"],
                "description": issue["fields"]["description"],
                "status": issue["fields"]["status"]["name"],
                "start_date": issue["fields"][self.jira_project.start_data_field_id],
                "due_date": issue["fields"]["duedate"]
            }
            for issue in epic_issues
        ]
    
    def get_in_progress_issues(self):
        # JQL to get all in-progress issues in project
        return self.get_issues_by_status_category("In Progress")

    def get_done_issues(self):
        # JQL to get all done issues in project
        return self.get_issues_by_status_category("Done")

    def get_issues_by_status_category(self, status_category: str) -> list[Issue]:
        jql = f"project={self.project} AND statusCategory='{status_category}' AND issuetype != Epic"
        return self.get_issues_by_jql(jql)

    def get_issues_by_jql(self, jql: str) -> list[Issue]:
        url = f"{self.base_url}/search/jql"
        params = {
            "jql": jql,
            "fields": f"summary,description,status,created,{self.jira_project.actual_start_date_field_id},{self.jira_project.actual_end_date_field_id}"
        }
        response = requests.get(url, headers=self.headers, params=params, auth=self.auth)
        response.raise_for_status()
        issues = response.json().get("issues", [])
        return [
            self.build_domain_issue(issue)
            for issue in issues
        ]

    def get_epic_with_issues(self, epic_key) -> Epic:
        # Get epic details
        url = f"{self.base_url}/issue/{epic_key}"
        params = {
            "fields": f"summary,description,status,{self.jira_project.start_data_field_id},duedate"
        }
        response = requests.get(url, headers=self.headers, params=params, auth=self.auth)
        response.raise_for_status()
        epic_response = response.json().get("fields", {})
        
        # Get issues linked to this epic
        children_of_epic_jql = f'"Epic Link"={epic_key}'
        issues_of_epic = self.get_issues_by_jql(children_of_epic_jql)
        
        # Map api response to domain objects
        epic = Epic()
        epic.key = epic_key
        epic.summary = epic_response.get("summary")
        epic.description = epic_response.get("description")
        epic.status = epic_response.get("status", {}).get("name")
        epic.start_date = epic_response.get(self.jira_project.start_data_field_id)
        epic.due_date = epic_response.get("duedate")
        epic.issues = issues_of_epic

        return epic
    
    def build_domain_issue(self, issue_response):
        issue = Issue()
        issue.issue_id = issue_response["key"]
        issue.title = issue_response["fields"]["summary"]
        issue.description = self._adf2textv2(issue_response["fields"]["description"])
        # issue.description = issue_response["fields"]["description"]
        issue.status = issue_response["fields"]["status"]["name"]
        # issue.done_date = self.get_done_date_from_changelog(issue.issue_id)
        issue.created_date = self._extract_date_from_iso_datetime(issue_response["fields"]["created"])
        issue.start_date = self._extract_date_from_iso_datetime(issue_response["fields"][self.jira_project.actual_start_date_field_id])
        issue.done_date = self._extract_date_from_iso_datetime(issue_response["fields"][self.jira_project.actual_end_date_field_id])
        return issue

    def _extract_date_from_iso_datetime(self, datetime_str: str) -> str:
        if datetime_str is None:
            return None

        if "T" in datetime_str:
            return datetime_str.split("T")[0]
        return datetime_str
    
    def _adf2textv2(self, data):
        """Convert Atlassian Document Format (ADF) to plain text."""
        if not data or 'content' not in data:
            return ""

        text = ""
        for content in data['content']:
            if content['type'] == 'paragraph':
                pass
            elif content['type'] == 'heading':
                text += "\n "
            elif content['type'] == 'listItem':
                text += "\n* "
            elif content['type'] == 'inlineCard':
                text += " ".join(content['attrs'].values())
            elif content['type'] == 'text':
                text += content['text']
            if 'content' in content.keys():
                text += self._adf2textv2(content)
        return text

    # def get_done_date_from_changelog(self, issue_key) -> str:
    #     # Get the status history for the issue
    #     url = f"{self.base_url}/issue/{issue_key}/changelog"
    #     response = requests.get(url, headers=self.headers, auth=self.auth)
    #     response.raise_for_status()
    #     changelog = response.json().get("values", [])
        
    #     # Find the date when the status was last updated to Done
    #     for change in changelog:
    #         for item in change.get("items", []):
    #             if item.get("field") == "status" and item.get("toString") == "Done":
    #                 return change.get("created")
        
    #     return None
