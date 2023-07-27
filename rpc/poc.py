from typing import Optional

from tools import auth
from tools import rpc_tools
from pylon.core.tools import web
from pylon.core.tools import log


class RPC:
    @web.rpc("list_user_projects", "list_user_projects")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def list_user_projects(self, user_id: int, **kwargs) -> list:
        all_projects = self.list(**kwargs)
        # log.info(f"projects {user_id=} {all_projects=}")
        user_projects = list()
        for project in all_projects:
            if self.context.rpc_manager.call.admin_check_user_in_project(project["id"], user_id):
                user_projects.append(project)
        return user_projects

    @web.rpc("add_user_to_project_or_create", "add_user_to_project_or_create")
    @rpc_tools.wrap_exceptions(RuntimeError)
    def add_user_to_project_or_create(
            self,
            user_email: str,
            project_id: int,
            roles: list[str],
    ):
        user = None
        user_email = user_email.lower()
        for i in auth.list_users():
            if i['email'] == user_email:
                user = i
                break
        if user:
            project_users = self.context.rpc_manager.call.admin_get_users_ids_in_project(project_id)
            user_exists = False
            for u in project_users:
                if user['id'] == u['auth_id']:
                    user_exists = True
                    break
            if user_exists:
                return {
                    'msg': f'user {user["email"]} already exists in project {project_id}',
                    'status': 'error',
                    'email': user["email"]
                }
            log.info('user %s found. adding to project', user)
            self.context.rpc_manager.call.admin_add_user_to_project(
                project_id, user['id'], roles
            )
            return {
                'msg': f'user {user["email"]} added to project {project_id}',
                'status': 'ok',
                'email': user["email"]
            }
        else:
            log.info('user %s not found. creating user', user_email)
            keycloak_token = self.context.rpc_manager.call.auth_manager_get_token()
            user_data = {
                "username": user_email,
                "email": user_email,
                "enabled": True,
                "totp": False,
                "emailVerified": False,
                "disableableCredentialTypes": [],
                "requiredActions": ["UPDATE_PASSWORD"],
                "notBefore": 0,
                "access": {
                    "manageGroupMembership": True,
                    "view": True,
                    "mapRoles": True,
                    "impersonate": True,
                    "manage": True
                },
                "credentials": [{
                    "type": "password",
                    "value": "11111111",
                    "temporary": True

                }, ]
            }
            log.info('creating keycloak entry')
            user = self.context.rpc_manager.call.auth_manager_create_user_representation(
                user_data=user_data
            )
            self.context.rpc_manager.call.auth_manager_post_user(
                realm='carrier', token=keycloak_token, entity=user
            )
            log.info('after keycloak')

            user_id = auth.add_user(user_email)
            # auth.add_user_provider(user_id, user_name)
            auth.add_user_provider(user_id, user_email)
            auth.add_user_group(user_id, 1)

            self.context.rpc_manager.call.admin_add_user_to_project(
                project_id, user_id, roles
            )
            return {
                'msg': f'user {user_email} created and added to project {project_id}',
                'status': 'ok',
                'email': user_email
            }
