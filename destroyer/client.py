"""
A further wrapper on the AzureDevops Python API to abstract commmon interactions
with Azure Devops such as checking if a release is complete.

Parameters:    
    access_cfg (AccessConfig): The configuration to access AzureDevOps.    

"""

from typing import Tuple, Union

from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

from destroyer.config import AccessConfig
import logging
import sys


class DevOpsClient:
    def __init__(self, access_cfg: AccessConfig):

        self.access_cfg = access_cfg
        self._connect()

    def is_release_complete(self, release_id: str, environment_id: int,
                            name: str) -> bool:
        """
        Checks to see if a release is complete for a specific environment.

        Will exit with an exit code of 1 it the status is rejected or cancelled. 

        Arguments:
            release_id (int): ID of the release in Azure DevOps.
            environment_id (int): ID of the environment in a specific release.
            name (str): Name of the release.

        Returns:
            True if a release has succeeded or partiallySucceeded otherwise False.
        
        """
        release_environment = self.release_client.get_release_environment(
            self.access_cfg.project,
            release_id=release_id,
            environment_id=environment_id)

        if release_environment.status == "rejected" or release_environment.status == "cancelled":
            logging.critical(
                f"Release {name} has failed to deploy. The status is {release_environment.status}"
            )
            sys.exit(1)

        return release_environment.status == "succeeded" or release_environment.status == "partiallySucceeded"

    def get_latest_release(
            self, name: str,
            env_name: str) -> Union[Tuple[None, None], Tuple[int, int]]:
        """
        Retrieves the latest release and environment id for a specific environment.
        Gets a list of all the releases for a specific release pipeline, loops
        through them and for each release looks for a matching environment and status.

        Arguments:
            name: (str) Name of the release pipeline.
            env_name (str): Name of the environment that the release was run.

        Returns:
            The ID of the release and environment that was either succeeded or partially succeeded.
            If nothing is found then None, None is returned

        """

        releases = self.release_client.get_releases(self.access_cfg.project,
                                                    search_text=name,
                                                    top=200).value

        for release in releases:

            if release.release_definition.name == name:

                result = self.release_client.get_release(
                    self.access_cfg.project, release_id=release.id)

                for environment in result.environments:

                    if environment.name == env_name and (
                            environment.status == "succeeded"
                            or environment.status == "partiallySucceeded"):
                        logging.info(
                            f"Found environment for {name} with id: {environment.id} "
                        )
                        return release.id, environment.id

        return None, None

    def run_release(self, release_id: int, environment_id: int) -> None:
        """
        Runs the latest succeeded or partically succeeded pipeline associated
        with the object.

        Arguments:
            release_id (int): Id of the release in Azure DevOps.
            environment_id (int): Id of the environment associated to a specific release.

        """

        start_values = {
            "comment": "Run by the DESTROYER",
            "status": "inProgress"
        }

        self.release_client.update_release_environment(start_values,
                                                       self.access_cfg.project,
                                                       release_id,
                                                       environment_id)

    def _connect(self):
        """
        Logins to the Azure DevOps API and sets the release_client.

        """
        credentials = BasicAuthentication("", self.access_cfg.access_token)
        connection = Connection(
            base_url=f"https://dev.azure.com/{self.access_cfg.organisation}/",
            creds=credentials)

        self.release_client = connection.clients_v5_1.get_release_client()