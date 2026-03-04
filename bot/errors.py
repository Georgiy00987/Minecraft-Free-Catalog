class EnvLoadError(Exception):
    def __init__(self, var_name: str):
        super().__init__(f"❌ Переменная окружения не задана: {var_name}")


class GitHubLoadError(Exception):
    def __init__(self):
        super().__init__("❌ Не удалось подключиться к GitHub")


class GitHubEnvError(Exception):
    def __init__(self):
        super().__init__("❌ GITHUB_REPO или GITHUB_TOKEN не заданы")

class CryptoBotEnvError(Exception):
    def __init__(self):
        super().__init__("❌ CRYPTOBOT_TOKEN не задан")
