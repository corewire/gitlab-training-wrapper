import yaml
import gitlab
import gitlab.exceptions


class GitlabBuilder:
    """
    This class is used by Corewire to deploy a Git trainings-env.
    Most likely it will be called from a terraform script
    as a fully automated deploy.
    """

    def __init__(self, config):
        self.conf_file = config
        self.config = None
        self.gl = None
        self.users = []
        self.groups = []
        self.usergroups = {}

    # Read the config
    def read_yaml(self):
        """
        read da config!
        :return: config as dict
        """
        with open(self.conf_file, 'r') as content_file:
            content = content_file.read()
        return content

    def connect(self):
        """
        Initiates a connection to the instance from the config File
        :return: API Instance of the given Gitlab
        """
        # Load the config into a Object
        config = yaml.load(self.read_yaml(), yaml.FullLoader)
        gl = gitlab.Gitlab(url=config["gitlab-url"], private_token=config["auth-token"])
        self.gl = gl
        self.config = config

    def create_users(self):
        """
        Applies the wanted User config to the Gitlab Instance
        :return: nothing
        """
        if self.gl is None:
            print("No config found, please run connect first.")
            exit(1)
        else:
            print("Starting Users creation.")
            gl = self.gl
            config = self.config
            for username in config["users"]:
                i = 0
                count = int(config["users"][username]["count"])
                pw = config["users"][username]["pass"]
                groups = config["users"][username]["groups"]
                while i < count:
                    i += 1
                    print("creating user: " + username + '-' + str(i) + " ...", end=' ')
                    user = gl.users.create({'email': username + str(i) + '@example.com',
                                            'password': pw,
                                            'username': username + '-' + str(i),
                                            'name': username + '-' + str(i),
                                            'skip_confirmation': True})
                    self.users.append(user)
                    self.usergroups[user.id] = groups
                    print("done.")
            print("All Users created!")

    def create_groups(self):
        if self.gl is None:
            print("No config found, please run connect first.")
        else:
            print("Starting Group creation ...")
            gl = self.gl
            config = self.config
            for groupname in config["groups"]:
                i = 0
                count = int(config["groups"][groupname]["count"])
                while i < count:
                    i += 1
                    if count == 1:
                        print("Adding group: " + groupname + " ... ", end='')
                        group = gl.groups.create({'name': groupname,
                                                  'path': groupname})
                        self.groups.append(group)
                        print("done.")
                    else:
                        print("Adding group: " + groupname + "-" + str(i) + " ... ", end='')
                        group = gl.groups.create({'name': groupname + "-" + str(i),
                                                  'path': groupname + "-" + str(i)})
                        self.groups.append(group)
                        print("done.")
                    for member_id, groupslist in self.usergroups.items():
                        for usr_group in groupslist:
                            gr_name, access_lvl = usr_group.split(":")
                            if access_lvl == "guest":
                                access_lvl_gl = gitlab.GUEST_ACCESS
                            elif access_lvl == "reporter":
                                access_lvl_gl = gitlab.REPORTER_ACCESS
                            elif access_lvl == "developer":
                                access_lvl_gl = gitlab.DEVELOPER_ACCESS
                            elif access_lvl == "maintainer":
                                access_lvl_gl = gitlab.MAINTAINER_ACCESS
                            elif access_lvl == "owner":
                                access_lvl_gl = gitlab.OWNER_ACCESS
                            else:
                                print("Unknown Access Rights for this group: " + gr_name + "\nAborting!")
                                exit(1)
                            if gr_name == groupname + "-" + str(i):
                                print("Adding Memer ID: " + str(
                                    member_id) + " to Group: " + gr_name + " with Rights: " + access_lvl + " ... ",
                                      end='')
                                group.members.create({'user_id': member_id,
                                                      'access_level': access_lvl_gl})
                                print("done")
                print("Group creation finished.")

    def create_projects(self):
        """
        Creates the Projects that are given from the config.yml
        :return:
        """
        if self.gl is None or self.config is None:
            print("No config/Gitlab found, please run connect first.")
            exit(1)
        else:
            print("Starting Project creation.")
            gl = self.gl
            config = self.config
            for project in config["projects"]:
                # get the import url
                imp_url = config["projects"][project]["import_url"]

                # Set rights/members/protected master
                if config["projects"][project]["owner_conf"]["owner"] == "all_users":
                    for user in self.users:
                        print("Importing \'" + imp_url + "\' for user \'" + user.username + "\'")
                        pj = user.projects.create({'name': project,
                                                   'user_id': user.id,
                                                   'access_level': gitlab.OWNER_ACCESS,
                                                   'import_url': imp_url})
                elif config["projects"][project]["owner_conf"]["owner"] == "user":
                    for user in self.users:
                        if user.username == config["projects"][project]["owner_conf"]["name"]:
                            print("Importing \'" + imp_url + "\' for user \'" + user.username + "\'")
                            pj = user.projects.create({'name': project,
                                                       'user_id': user.id,
                                                       'Access_level': gitlab.OWNER_ACCESS,
                                                       'import_url': imp_url})
                elif config["projects"][project]["owner_conf"]["owner"] == "group":
                    for group in self.groups:
                        if group.name == config["projects"][project]["owner_conf"]["name"]:
                            print("Importing \'" + imp_url + "\' for group \'" + group.name + "\'")
                            pj = group.projects.create({'name': project,
                                                        'namespace_id': group.id,
                                                        'import_url': imp_url})
                else:
                    print("Project owner Config is wrong, aborting")
                    exit(1)
                # Delete protected Master Branch
                if config["projects"][project]["protect_master_branch"] == "False":
                    print("Removing Project master Branch protection")
                    pj.protectedbranches.delete('master')


if __name__ == "__main__":
    gl_instance = GitlabBuilder('config.yml')
    gl_instance.connect()
    gl_instance.create_users()
    gl_instance.create_groups()
    gl_instance.create_projects()
