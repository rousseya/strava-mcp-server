import os

from dotenv import load_dotenv
from stravalib.client import Client

load_dotenv()


class StravaClient:
    def __init__(self):
        self.client = Client()
        self.client_id = os.getenv("STRAVA_CLIENT_ID")
        self.client_secret = os.getenv("STRAVA_CLIENT_SECRET")
        self.refresh_token = os.getenv("STRAVA_REFRESH_TOKEN")
        access_token = os.getenv("STRAVA_ACCESS_TOKEN")

        if not all([self.client_id, self.client_secret, self.refresh_token, access_token]):
            raise RuntimeError("Missing Strava credentials in environment variables")

        self.client.access_token = access_token
        self.client.refresh_token = self.refresh_token
        self.client.client_id = self.client_id
        self.client.client_secret = self.client_secret

    def refresh_access_token(self) -> dict | None:
        tokens = self.client.refresh_access_token(
            client_id=self.client_id,
            client_secret=self.client_secret,
            refresh_token=self.refresh_token,
        )
        if tokens:
            self.client.access_token = tokens.get("access_token", self.client.access_token)
            self.client.refresh_token = tokens.get("refresh_token", self.client.refresh_token)
        return tokens

    def get_activities(self, limit: int = 30):
        self.refresh_access_token()
        return list(self.client.get_activities(limit=limit))

    def get_activity(self, activity_id: int):
        self.refresh_access_token()
        return self.client.get_activity(activity_id)

    def get_stats(self):
        self.refresh_access_token()
        athlete = self.client.get_athlete()
        if not athlete:
            return None
        return self.client.get_athlete_stats(athlete.id)

    def update_activity(self, activity_id: int, **kwargs):
        """Update an activity with the given parameters.

        Args:
            activity_id: The Strava activity ID.
            **kwargs: Activity fields to update (name, type, sport_type, description, etc.)

        Returns:
            The updated activity.
        """
        self.refresh_access_token()
        return self.client.update_activity(activity_id, **kwargs)
